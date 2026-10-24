/**
 * The review "thinking" loader (REV-005 loader UX). While Stockfish analyses a
 * game, this replaces a static text card with a live board that replays the
 * game *backwards* ply by ply — pieces visibly walk back toward the opening —
 * then loops, until the analysis resolves and the page lands on move one.
 *
 * Positions come from `fens` when the page already has a review (the
 * re-analyse case), otherwise from a single game fetch replayed forward with
 * `forwardFens`. A missing, empty or failed game falls back to a static
 * start-position board, and the `role="status"` line stays for screen readers.
 */
import { useEffect, useMemo, useState } from 'react';

import Chessboard from './Chessboard';
import { api } from '../lib/api-client';
import { allSquares, forwardFens, parseFenPlacement } from '../lib/chess';

/** How long each reversed ply holds before stepping back to the previous one. */
const REVERSE_STEP_MS = 450;
const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

type Props = {
  gameId: number;
  /** Positions to walk; when omitted the component fetches and replays the game. */
  fens?: string[];
};

/**
 * The squares the ply that produced `next` moved between, read by diffing two
 * consecutive FEN placements. Returns null when the step is ambiguous (a
 * capture, castle or promotion changed more than one square) — a missing
 * highlight is harmless, the board still visibly changes position.
 */
function movedSquares(prev: string, next: string): { from: string; to: string } | null {
  const before = parseFenPlacement(prev);
  const after = parseFenPlacement(next);
  const key = (sq: string, map: Map<string, { kind: string; color: string }>) => {
    const piece = map.get(sq);
    return piece ? `${piece.color}${piece.kind}` : '';
  };
  let from: string | null = null;
  let to: string | null = null;
  for (const sq of allSquares()) {
    const was = key(sq, before);
    const is = key(sq, after);
    if (was === is) continue;
    if (was && !is) from = sq;
    else if (!was && is) to = sq;
    else return null; // piece type changed or a capture: too ambiguous to name
  }
  return from && to ? { from, to } : null;
}

export default function ReviewThinking({ gameId, fens }: Props) {
  const supplied = fens && fens.length > 0;
  const [fetched, setFetched] = useState<string[]>([]);
  const positions = supplied ? (fens as string[]) : fetched;
  const count = positions.length;

  // Fetch the game once, only when the page has no review positions to show.
  useEffect(() => {
    if (supplied) return;
    let cancelled = false;
    api
      .getGame(gameId)
      .then((game) => {
        if (!cancelled) setFetched(forwardFens(game.moves));
      })
      .catch(() => {
        if (!cancelled) setFetched([]);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, supplied]);

  // Start at the newest position and step backwards, looping at the opening.
  // Resetting the cursor when the position list arrives is the documented
  // "adjust state during render" pattern — it is derived from a prop change,
  // so it belongs here rather than in an effect.
  const [cursorSource, setCursorSource] = useState<string[]>(positions);
  const [index, setIndex] = useState(() => Math.max(0, positions.length - 1));
  if (cursorSource !== positions) {
    setCursorSource(positions);
    setIndex(Math.max(0, count - 1));
  }

  useEffect(() => {
    if (count === 0) return;
    const timer = setInterval(() => {
      setIndex((cur) => (cur <= 0 ? count - 1 : cur - 1));
    }, REVERSE_STEP_MS);
    return () => clearInterval(timer);
  }, [count]);

  const currentFen = positions[index] ?? START_FEN;
  const lastMove = useMemo(() => {
    const previous = positions[index - 1];
    return previous ? movedSquares(previous, currentFen) : null;
  }, [positions, index, currentFen]);

  return (
    <div className="review-thinking">
      <Chessboard
        fen={currentFen}
        status="active"
        selected={null}
        onSelect={() => {}}
        onMove={() => {}}
        disabled
        lastMove={lastMove}
      />
      <p className="u-muted" role="status">
        Stockfish is replaying every move. Long games can take a minute.
      </p>
    </div>
  );
}
