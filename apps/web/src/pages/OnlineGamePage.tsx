/**
 * Online game page (online-plan §6): the same server-authoritative board as
 * GamePage, driven by WebSocket state broadcasts with a REST polling fallback
 * when the socket is down. Moves are only accepted for the player's own color
 * — the server double-checks the turn (and everything else).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import Chessboard from '../components/Chessboard';
import GameStatusBanner from '../components/GameStatus';
import MoveHistory from '../components/MoveHistory';
import PlayerInfo from '../components/PlayerInfo';
import SoundToggle from '../components/SoundToggle';
import ConfirmDialog from '../components/ui/Modal';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useAuth } from '../app/useAuth';
import { useAchievementsOptional } from '../app/useAchievements';
import { useAchievementRide } from '../app/useAchievementRide';
import { ApiError, api } from '../lib/api-client';
import { capturedPieces, materialBalance, sideToMove } from '../lib/chess';
import { emitError, emitSelect } from '../lib/game-events';
import { useGameFeedback } from '../lib/useGameFeedback';
import type { GameResponse } from '../lib/api-types';
import { OnlineSocket, type WsEvent } from '../lib/online-ws';

const POLL_MS = 3000;

export default function OnlineGamePage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();

  const [game, setGame] = useState<GameResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<'resign' | null>(null);
  const socketRef = useRef<OnlineSocket | null>(null);

  const gameId = Number(id);
  const badId = !Number.isFinite(gameId);
  // Private socket unlocks arrive outside the response ride, so this page
  // needs the queue itself — optionally, so it still renders without a provider.
  const celebrate = useAchievementsOptional()?.celebrate;

  useEffect(() => {
    if (badId) return;
    let cancelled = false;
    api
      .getOnlineGame(gameId)
      .then((g) => {
        if (!cancelled) setGame(g);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load game');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, badId]);

  // Socket lifecycle: one per game per mount; REST polling covers outages.
  // Keyed on `hasGame` (not `game`) so state broadcasts never re-connect.
  const hasGame = game !== null;
  useEffect(() => {
    if (badId || loading || !hasGame) return;
    const socket = new OnlineSocket(
      gameId,
      (event: WsEvent) => {
        if (event.type === 'game_state') {
          setGame(event.payload);
          setError(null);
          setSelected(null);
        } else if (event.type === 'opponent_joined') {
          setNotice('Opponent connected.');
        } else if (event.type === 'opponent_left') {
          setNotice('Opponent disconnected — they still get your moves over REST.');
        } else if (event.type === 'achievement') {
          // Private to this seat: the server never broadcasts unlocks (§6).
          celebrate?.(event.payload.items);
        } else if (event.type === 'error') {
          // A rejected action is felt, not read (wrong move → error sound only).
          emitError();
        }
      },
      setConnected,
    );
    socketRef.current = socket;
    socket.connect();
    return () => {
      socketRef.current = null;
      socket.close();
    };
  }, [gameId, badId, loading, hasGame, celebrate]);

  const finished = game !== null && game.status !== 'active';
  useEffect(() => {
    if (badId || loading || finished || connected) return;
    const timer = setInterval(() => {
      api
        .getOnlineGame(gameId)
        .then(setGame)
        .catch(() => {
          /* transient poll failure keeps the last known state */
        });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [gameId, badId, loading, finished, connected]);

  const myColor = useMemo(() => {
    if (!game || !user) return null;
    if (game.white_user_id === user.id) return 'w';
    if (game.black_user_id === user.id) return 'b';
    return null;
  }, [game, user]);

  const sendOrRest = useCallback(
    async (action: 'move' | 'resign' | 'draw_claim', g: GameResponse, uci?: string) => {
      setBusy(true);
      setError(null);
      try {
        if (action === 'move') {
          const sent = socketRef.current?.send({
            type: 'move',
            payload: { uci: uci ?? '', expected_version: g.version },
          });
          if (!sent)
            setGame(
              await api.submitOnlineMove(gameId, { uci: uci ?? '', expected_version: g.version }),
            );
        } else {
          const sent = socketRef.current?.send({ type: action });
          if (!sent) {
            setGame(
              action === 'resign'
                ? await api.resignOnlineGame(gameId)
                : await api.claimOnlineDraw(gameId),
            );
          }
        }
        setSelected(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          try {
            setGame(await api.getOnlineGame(gameId));
          } catch {
            /* keep existing state on resync failure */
          }
        }
        // A rejected move is felt, not read: error sound, no banner.
        if (action === 'move' && err instanceof ApiError && err.status === 422) {
          emitError();
        } else {
          setError(err instanceof ApiError ? err.message : 'Action failed');
        }
      } finally {
        setBusy(false);
      }
    },
    [gameId],
  );

  const handleMove = useCallback(
    (from: string, to: string, promotion?: string) => {
      if (!game) return;
      void sendOrRest('move', game, `${from}${to}${promotion ?? ''}`);
    },
    [game, sendOrRest],
  );

  // Move feedback for broadcasts, REST fallback, and the opponent's plies.
  useGameFeedback(game);
  // Achievements unlocked by this seat's own action (ACH-006).
  useAchievementRide(game);

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
        <Link to="/lobby">← Lobby</Link>
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
        <Link to="/lobby">Back to lobby</Link>
      </main>
    );
  if (!game) return null;

  const turn = sideToMove(game.fen);
  const myTurn = myColor !== null && turn === myColor && !finished;
  const inCheck = game.fen.includes('+') || game.status === 'checkmate';

  return (
    <main id="main-content" className="game-page">
      <header className="game-header">
        <Link to="/lobby" className="back-link">
          ← Lobby
        </Link>
        <h1 className="game-title">Online game #{game.id}</h1>
        <div className="game-tags">
          <span className="badge">
            You play {myColor === 'b' ? 'Black' : myColor === 'w' ? 'White' : 'a spectator'}
          </span>
          <span className={connected ? 'badge badge-accent' : 'badge badge-warning'}>
            {connected ? 'Live' : 'Polling'}
          </span>
          <GameStatusBanner status={game.status} inCheck={inCheck} />
          {finished && game.moves.length > 0 && (
            <Link
              to={`/games/${game.id}/review`}
              state={{ backTo: `/online/${game.id}` }}
              className="badge badge-accent"
            >
              Review game
            </Link>
          )}
        </div>
      </header>
      {error && (
        <p role="alert" className="error" style={{ marginBottom: 'var(--space-4)' }}>
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="loading-state" style={{ marginBottom: 'var(--space-4)' }}>
          {notice}
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
              onSelect={(square) => {
                if (square) emitSelect();
                setSelected(square);
              }}
              onMove={handleMove}
              disabled={busy || !myTurn}
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
          <Card>
            <h2>Moves</h2>
            <MoveHistory moves={game.moves} />
          </Card>
          <Card>
            <h2>Actions</h2>
            <div className="game-actions">
              <SoundToggle />
              <Button
                variant="ghost"
                onClick={() => void sendOrRest('draw_claim', game)}
                disabled={busy || finished}
                title={finished ? 'The game is over' : undefined}
              >
                Claim draw
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
            <p className="hint" style={{ marginTop: 'var(--space-4)' }}>
              The server validates every move and turn. Broadcasts arrive on the socket; if it
              drops, the page falls back to polling.
            </p>
          </Card>
        </aside>
      </div>
      {pendingConfirm === 'resign' && (
        <ConfirmDialog
          title="Resign this game?"
          description="Resigning ends the game immediately and scores the win for your opponent."
          confirmLabel="Resign game"
          confirmTone="danger"
          onConfirm={() => {
            setPendingConfirm(null);
            void sendOrRest('resign', game);
          }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
    </main>
  );
}
