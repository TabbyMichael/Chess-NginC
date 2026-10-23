/**
 * Chessboard (WEB-010/011/013/014/027): click-to-select + click-to-move,
 * drag & drop, promotion picker, keyboard operable, turn indicator.
 * Selected pieces preview their legal destinations (subtle dots/rings via
 * chess.js) — a beginner aid only; the server stays authoritative on legality
 * (invalid moves surface as 422 errors). Coordinates render only on the edge
 * files/ranks.
 */
import { useEffect, useMemo, useState, type DragEvent } from 'react';

import PieceIcon from './PieceIcon';
import {
  allSquares,
  isLightSquare,
  legalTargets,
  parseFenPlacement,
  sideToMove,
} from '../lib/chess';

type Props = {
  fen: string;
  status: string;
  selected: string | null;
  onSelect: (square: string | null) => void;
  onMove: (from: string, to: string, promotion?: string) => void;
  disabled?: boolean;
  lastMove?: { from: string; to: string } | null;
  inCheck?: boolean;
};

const PROMOTION_PIECE_KINDS = ['q', 'r', 'b', 'n'] as const;

function getPieceColor(color: string): 'white' | 'black' {
  return color === 'w' ? 'white' : 'black';
}

export default function Chessboard({
  fen,
  status,
  selected,
  onSelect,
  onMove,
  disabled = false,
  lastMove,
  inCheck = false,
}: Props) {
  const board = useMemo(() => parseFenPlacement(fen), [fen]);
  const turn = sideToMove(fen);
  // Legal-destination preview for the currently selected piece.
  const hints = useMemo(() => {
    if (!selected || disabled || status !== 'active') return null;
    const targets = legalTargets(fen, selected);
    return targets.length ? new Set(targets) : null;
  }, [selected, fen, status, disabled]);
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(
    null,
  );
  const [dragOver, setDragOver] = useState<string | null>(null);
  useEffect(() => () => setDragOver(null), []);
  const turnLabel =
    status !== 'active' ? `Game over: ${status}` : `Turn: ${turn === 'w' ? 'White' : 'Black'}`;
  function isPromotionMove(from: string, to: string): boolean {
    const piece = board.get(from);
    if (!piece || piece.kind !== 'p') return false;
    const toRank = to[1];
    return (piece.color === 'w' && toRank === '8') || (piece.color === 'b' && toRank === '1');
  }
  function handleSquareClick(square: string) {
    if (disabled || status !== 'active') return;
    if (pendingPromotion) return;
    if (selected === null) {
      if (board.has(square)) onSelect(square);
      return;
    }
    if (selected === square) {
      onSelect(null);
      return;
    }
    if (isPromotionMove(selected, square)) {
      setPendingPromotion({ from: selected, to: square });
      return;
    }
    onMove(selected, square);
    onSelect(null);
  }
  function handleKey(square: string, key: string) {
    if (key === 'Enter' || key === ' ') {
      handleSquareClick(square);
    } else if (key === 'Escape') {
      onSelect(null);
      setPendingPromotion(null);
    }
  }
  function handleDragStart(square: string, event: DragEvent<HTMLButtonElement>) {
    if (disabled || status !== 'active') {
      event.preventDefault();
      return;
    }
    onSelect(square);
  }
  function handleDragOver(square: string, event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (dragOver !== square) setDragOver(square);
  }
  function handleDrop(to: string, event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragOver(null);
    const from = selected;
    if (!from || from === to || disabled || status !== 'active') return;
    if (isPromotionMove(from, to)) {
      setPendingPromotion({ from, to });
      return;
    }
    onMove(from, to);
    onSelect(null);
  }

  const lastFrom = lastMove?.from;
  const lastTo = lastMove?.to;
  return (
    <section aria-label="chessboard">
      <p role="status" aria-live="polite" className="board-status">
        {turnLabel}
        {disabled && status === 'active' && <span className="busy"> · updating…</span>}
      </p>
      <div
        className="board-wrapper"
        role="grid"
        aria-label={`Chess position, ${turn === 'w' ? 'white' : 'black'} to move`}
      >
        <div className="board">
          {allSquares().map((square) => {
            const piece = board.get(square);
            const isSelected = selected === square;
            const isDraggable = !disabled && status === 'active' && Boolean(piece);
            const hint = hints?.has(square) ? (piece ? 'hint-capture' : 'hint-target') : '';
            return (
              <button
                key={square}
                type="button"
                role="gridcell"
                aria-label={`${square}${piece ? `, ${piece.color === 'w' ? 'white' : 'black'} ${piece.kind}` : ', empty'}${isSelected ? ', selected' : ''}`}
                aria-pressed={isSelected}
                draggable={isDraggable}
                className={[
                  'square',
                  isLightSquare(square) ? 'light' : 'dark',
                  isSelected ? 'selected' : '',
                  lastFrom === square || lastTo === square ? 'last-move' : '',
                  inCheck && piece?.kind === 'k' ? 'in-check' : '',
                  dragOver === square ? 'dragover' : '',
                  hint,
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => handleSquareClick(square)}
                onKeyDown={(e) => handleKey(square, e.key)}
                onDragStart={(e) => handleDragStart(square, e)}
                onDragOver={(e) => handleDragOver(square, e)}
                onDragLeave={() => setDragOver((cur) => (cur === square ? null : cur))}
                onDrop={(e) => handleDrop(square, e)}
                disabled={disabled}
              >
                {piece && (
                  <PieceIcon
                    kind={piece.kind}
                    color={piece.color}
                    className={`piece ${getPieceColor(piece.color)}`}
                  />
                )}
                {square[0] === 'a' && (
                  <span className="coord coord-rank" aria-hidden="true">
                    {square[1]}
                  </span>
                )}
                {square[1] === '1' && (
                  <span className="coord coord-file" aria-hidden="true">
                    {square[0]}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
      {pendingPromotion && (
        <div
          className="promotion-overlay"
          onClick={() => {
            setPendingPromotion(null);
            onSelect(null);
          }}
        >
          <div
            role="dialog"
            aria-label="choose promotion piece"
            className="promotion-picker"
            onClick={(e) => e.stopPropagation()}
          >
            <p>
              Promote {pendingPromotion.from} → {pendingPromotion.to} to:
            </p>
            <div className="promotion-grid">
              {PROMOTION_PIECE_KINDS.map((kind) => (
                <button
                  key={kind}
                  type="button"
                  aria-label={`promote to ${kind}`}
                  onClick={() => {
                    onMove(pendingPromotion.from, pendingPromotion.to, kind);
                    setPendingPromotion(null);
                    onSelect(null);
                  }}
                >
                  <PieceIcon
                    kind={kind}
                    color={board.get(pendingPromotion.from)?.color ?? 'w'}
                    className={`piece ${
                      board.get(pendingPromotion.from)?.color === 'w' ? 'white' : 'black'
                    }`}
                  />
                </button>
              ))}
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={() => {
                setPendingPromotion(null);
                onSelect(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
