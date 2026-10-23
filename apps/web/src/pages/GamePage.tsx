/**
 * Game page (WEB-010..019, WEB-024/025): board, move submission, undo,
 * resign, draw-claim, engine moves, resume via GET game.
 * Board-first layout: compact header, player bars around the board,
 * side panel with move history and grouped actions. Destructive actions
 * (resign, reset) ask for confirmation first.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useLocation, useParams } from 'react-router-dom';
import { Coins } from 'lucide-react';

import Chessboard from '../components/Chessboard';
import GameStatusBanner from '../components/GameStatus';
import MoveHistory from '../components/MoveHistory';
import PlayerInfo from '../components/PlayerInfo';
import ConfirmDialog from '../components/ui/Modal';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { ApiError, api } from '../lib/api-client';
import { capturedPieces, materialBalance, sideToMove } from '../lib/chess';
import type { GameResponse } from '../lib/api-types';

type PendingConfirm = 'resign' | 'reset' | null;

export default function GamePage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const initialDepth = (location.state as { depth?: number } | null)?.depth ?? 3;

  const [game, setGame] = useState<GameResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm>(null);
  const [points, setPoints] = useState<number | null>(null);
  // Game version for which the engine reply was already auto-requested.
  const autoEngineVersion = useRef<number | null>(null);

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

  // Engine answers automatically: whenever a computer game is live and it is
  // Black's turn (after the player's move, on resume, or after a 409 resync),
  // request one engine move per game version. The manual button stays as a
  // fallback if the automatic request fails.
  useEffect(() => {
    if (!game || busy) return;
    const engineToMove =
      game.mode === 'computer' && game.status === 'active' && sideToMove(game.fen) === 'b';
    if (!engineToMove) return;
    if (autoEngineVersion.current === game.version) return;
    autoEngineVersion.current = game.version;
    void run((g) =>
      api.engineMove(gameId, {
        expected_version: g.version,
        max_depth: initialDepth,
        max_time_ms: 2000,
      }),
    );
  }, [game, busy, run, gameId, initialDepth]);

  // Keep the points display live: refresh after each game-state change.
  const lastPointsVersion = useRef<number | null>(null);
  useEffect(() => {
    if (!game || game.mode !== 'computer') return;
    if (lastPointsVersion.current === game.version) return;
    lastPointsVersion.current = game.version;
    void api
      .me()
      .then((u) => setPoints(u.points))
      .catch(() => {
        /* points are cosmetic; keep the previous value on failure */
      });
  }, [game]);

  const handleReset = useCallback(async () => {
    if (!game) return;
    setPendingConfirm(null);
    setBusy(true);
    setError(null);
    try {
      let current = game;
      while (current.moves.length > 0) {
        const next = await api.undoMove(gameId, { expected_version: current.version });
        if (next.moves.length >= current.moves.length) break;
        current = next;
      }
      setGame(current);
      setSelected(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Reset failed');
    } finally {
      setBusy(false);
    }
  }, [game, gameId]);

  // Hooks must run unconditionally, so derive captures from `game?.fen`.
  const captures = useMemo(
    () => (game ? capturedPieces(game.fen) : { capturedByWhite: [], capturedByBlack: [] }),
    [game],
  );
  const material = useMemo(() => (game ? materialBalance(game.fen) : 0), [game]);

  if (badId) {
    return (
      <main id="main-content">
        <p role="alert" className="error">
          Invalid game id.
        </p>
        <Link to="/">← All games</Link>
      </main>
    );
  }
  if (loading)
    return (
      <main id="main-content">
        <p role="status" className="loading-state">
          Loading game…
        </p>
      </main>
    );
  if (error && !game)
    return (
      <main id="main-content">
        <p role="alert" className="error">
          {error}
        </p>
        <Link to="/">Back to dashboard</Link>
      </main>
    );
  if (!game) return null;
  // Online games can only be played through /online/:id (the legacy routes
  // refuse them server-side); redirect stale deep links to the right board.
  if (game.mode === 'online') {
    return <Navigate to={`/online/${game.id}`} replace />;
  }

  const inCheck = game.fen.includes('+') || game.status === 'checkmate';
  const finished = game.status !== 'active';
  const turn = sideToMove(game.fen);
  const noMoves = game.moves.length === 0;

  return (
    <main id="main-content" className="game-page">
      <header className="game-header">
        <Link to="/" className="back-link">
          ← All games
        </Link>
        <h1 className="game-title">Game #{game.id}</h1>
        <div className="game-tags">
          <span className="badge">
            {game.mode === 'computer'
              ? `Player vs Computer · depth ${initialDepth}`
              : 'Two players'}
          </span>
          <GameStatusBanner status={game.status} inCheck={inCheck} />
        </div>
      </header>
      {error && (
        <p role="alert" className="error" style={{ marginBottom: 'var(--space-4)' }}>
          {error}
        </p>
      )}
      <div className="game-layout">
        <div className="board-column">
          <PlayerInfo
            color="black"
            isTurn={turn === 'b'}
            finished={finished}
            captured={captures.capturedByBlack}
            materialBalance={material}
          />
          <div className="board-frame">
            <Chessboard
              fen={game.fen}
              status={game.status}
              selected={selected}
              onSelect={setSelected}
              onMove={handleMove}
              disabled={busy}
              lastMove={
                game.moves.length > 0
                  ? {
                      from: game.moves[game.moves.length - 1].uci.slice(0, 2),
                      to: game.moves[game.moves.length - 1].uci.slice(2, 4),
                    }
                  : null
              }
              inCheck={inCheck}
            />
          </div>
          <PlayerInfo
            color="white"
            isTurn={turn === 'w'}
            finished={finished}
            captured={captures.capturedByWhite}
            materialBalance={material}
          />
        </div>
        <aside className="game-sidebar" aria-label="game panel">
          {game.mode === 'computer' && (
            <Card>
              <div className="card-title">
                <h2>Points</h2>
                <span className="badge badge-accent">
                  <Coins size={13} aria-hidden="true" />
                  {points === null ? '—' : points.toLocaleString()}
                </span>
              </div>
              <p className="points-rules">
                +1 per move · win +10 · draw +5 · loss +3. Every move is recorded in the list above.
              </p>
            </Card>
          )}
          <Card>
            <h2>Moves</h2>
            <MoveHistory moves={game.moves} />
          </Card>
          <Card>
            <h2>Actions</h2>
            <div className="game-actions">
              <div className="action-row">
                <Button
                  variant="ghost"
                  onClick={() =>
                    void run((g) => api.undoMove(gameId, { expected_version: g.version }))
                  }
                  disabled={busy || finished || noMoves}
                  title={
                    finished ? 'The game is over' : noMoves ? 'Nothing to undo yet' : undefined
                  }
                >
                  Undo
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => void run(() => api.claimDraw(gameId))}
                  disabled={busy || finished}
                  title={finished ? 'The game is over' : undefined}
                >
                  Claim draw
                </Button>
              </div>
              {game.mode === 'computer' && (
                <Button
                  variant="primary"
                  onClick={() =>
                    void run((g) =>
                      api.engineMove(gameId, {
                        expected_version: g.version,
                        max_depth: initialDepth,
                        max_time_ms: 2000,
                      }),
                    )
                  }
                  disabled={busy || finished}
                  title={finished ? 'The game is over' : undefined}
                >
                  Engine move (depth {initialDepth})
                </Button>
              )}
              <div className="action-row">
                <Button
                  variant="ghost"
                  onClick={() => setPendingConfirm('reset')}
                  disabled={busy || finished || noMoves}
                  title={
                    finished ? 'The game is over' : noMoves ? 'Already at the start' : undefined
                  }
                >
                  Reset to start
                </Button>
                <Button
                  variant="danger"
                  onClick={() => setPendingConfirm('resign')}
                  disabled={busy || finished}
                  title={finished ? 'The game is over' : undefined}
                >
                  Resign
                </Button>
              </div>
            </div>
            <p className="hint" style={{ marginTop: 'var(--space-4)' }}>
              Click a piece, then its destination. Promotions ask which piece.
            </p>
          </Card>
        </aside>
      </div>
      {pendingConfirm === 'resign' && (
        <ConfirmDialog
          title="Resign this game?"
          description="Resigning ends the game immediately and cannot be undone."
          confirmLabel="Resign game"
          confirmTone="danger"
          onConfirm={() => {
            setPendingConfirm(null);
            void run(() => api.resignGame(gameId));
          }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
      {pendingConfirm === 'reset' && (
        <ConfirmDialog
          title="Reset to the starting position?"
          description="Every move in this game will be undone."
          confirmLabel="Reset game"
          onConfirm={() => void handleReset()}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
    </main>
  );
}
