/**
 * Game page (WEB-010..019, WEB-024/025): board, move submission, undo,
 * resign, draw-claim, engine moves, resume via GET game.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';

import Chessboard from '../components/Chessboard';
import GameStatusBanner from '../components/GameStatus';
import MoveHistory from '../components/MoveHistory';
import { ApiError, api } from '../lib/api-client';
import { capturedPieces } from '../lib/chess';
import type { GameResponse } from '../lib/api-types';

export default function GamePage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const initialDepth = (location.state as { depth?: number } | null)?.depth ?? 3;

  const [game, setGame] = useState<GameResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const gameId = Number(id);
  const badId = !Number.isFinite(gameId);

  useEffect(() => {
    if (badId) return;
    let cancelled = false;
    api
      .getGame(gameId)
      .then((g) => {
        if (!cancelled) setGame(g);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load game');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, badId]);

  const run = useCallback(
    async (fn: (g: GameResponse) => Promise<GameResponse>) => {
      if (!game || busy) return;
      setBusy(true);
      setError(null);
      try {
        setGame(await fn(game));
        setSelected(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          // Stale version: re-fetch then surface the message (WEB-025).
          try {
            setGame(await api.getGame(gameId));
          } catch {
            /* keep existing state on refetch failure */
          }
        }
        setError(err instanceof ApiError ? err.message : 'Action failed');
      } finally {
        setBusy(false);
      }
    },
    [game, busy, gameId],
  );

  const handleMove = useCallback(
    (from: string, to: string, promotion?: string) => {
      // UCI promotion moves always carry a piece letter; the picker defaults to 'q'.
      const uci = `${from}${to}${promotion ?? ''}`;
      void run((g) => api.submitMove(gameId, { uci, expected_version: g.version }));
    },
    [run, gameId],
  );

  // Hooks must run unconditionally, so derive captures from `game?.fen`.
  const captures = useMemo(
    () => (game ? capturedPieces(game.fen) : { capturedByWhite: [], capturedByBlack: [] }),
    [game],
  );

  if (badId) {
    return (
      <main>
        <p role="alert" className="error">
          Invalid game id.
        </p>
        <Link to="/">← All games</Link>
      </main>
    );
  }
  if (loading) return <p role="status">Loading game…</p>;
  if (error && !game)
    return (
      <main>
        <p role="alert" className="error">
          {error}
        </p>
        <Link to="/">Back to dashboard</Link>
      </main>
    );
  if (!game) return null;

  const inCheck = game.fen.includes('+') || game.status === 'checkmate';
  const finished = game.status !== 'active';

  return (
    <main className="game-page">
      <Link to="/">← All games</Link>
      <h1>
        Game #{game.id} ({game.mode})
      </h1>
      <GameStatusBanner status={game.status} inCheck={inCheck} />
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="game-layout">
        <Chessboard
          fen={game.fen}
          status={game.status}
          selected={selected}
          onSelect={setSelected}
          onMove={handleMove}
          disabled={busy}
        />
        <aside aria-label="game panel">
          <h2>Moves</h2>
          <MoveHistory moves={game.moves} />
          <section aria-label="captured pieces">
            <p className="hint">Captured by White</p>
            <p className="captures" aria-label="captured by white">
              {captures.capturedByWhite.join(' ') || '—'}
            </p>
            <p className="hint">Captured by Black</p>
            <p className="captures" aria-label="captured by black">
              {captures.capturedByBlack.join(' ') || '—'}
            </p>
          </section>
          <div className="controls">
            <button
              type="button"
              disabled={busy || finished || game.moves.length === 0}
              onClick={() => void run((g) => api.undoMove(gameId, { expected_version: g.version }))}
            >
              Undo
            </button>
            <button
              type="button"
              disabled={busy || finished || game.moves.length === 0}
              title="Undo every move to restart this game"
              onClick={async () => {
                if (!game) return;
                setBusy(true);
                setError(null);
                try {
                  // The API has no bulk-reset; undo until the server reports
                  // an empty move list (WEB-019). Loop on the refetched state,
                  // not the original snapshot.
                  let current = game;
                  while (current.moves.length > 0) {
                    const next = await api.undoMove(gameId, {
                      expected_version: current.version,
                    });
                    if (next.moves.length >= current.moves.length) break; // no progress
                    current = next;
                  }
                  setGame(current);
                  setSelected(null);
                } catch (err) {
                  setError(err instanceof ApiError ? err.message : 'Reset failed');
                } finally {
                  setBusy(false);
                }
              }}
            >
              Reset to start
            </button>
            <button
              type="button"
              disabled={busy || finished}
              onClick={() => void run(() => api.resignGame(gameId))}
            >
              Resign
            </button>
            <button
              type="button"
              disabled={busy || finished}
              onClick={() => void run(() => api.claimDraw(gameId))}
            >
              Claim draw
            </button>
            {game.mode === 'computer' && (
              <button
                type="button"
                disabled={busy || finished}
                onClick={() =>
                  void run((g) =>
                    api.engineMove(gameId, {
                      expected_version: g.version,
                      max_depth: initialDepth,
                      max_time_ms: 2000,
                    }),
                  )
                }
              >
                Engine move (depth {initialDepth})
              </button>
            )}
          </div>
          <p className="hint">
            Click a piece, then its destination. Promotions ask which piece. The server validates
            every move.
          </p>
        </aside>
      </div>
    </main>
  );
}
