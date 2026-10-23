/**
 * Online lobby (online-plan §5): queue for a match, watch queue state,
 * cancel, and jump into the game the moment pairing happens. The queue is
 * matched server-side; this page just polls the no-side-effect status route.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LoaderCircle, LogOut, Play, Swords } from 'lucide-react';

import { ApiError, api } from '../lib/api-client';
import type { GameResponse, QueueResponse } from '../lib/api-types';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

const POLL_MS = 2000;

export default function LobbyPage() {
  const navigate = useNavigate();
  const [queue, setQueue] = useState<QueueResponse>({ status: 'idle' });
  const [games, setGames] = useState<GameResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  // True while this page holds a queue slot: unmount must not strand it.
  const queuedRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  const applyQueue = useCallback(
    (body: QueueResponse) => {
      setQueue(body);
      if (body.status === 'matched' && body.game_id) {
        queuedRef.current = false;
        stopPolling();
        navigate(`/online/${body.game_id}`);
      } else {
        queuedRef.current = body.status === 'queued';
      }
    },
    [navigate, stopPolling],
  );

  const startPolling = useCallback(() => {
    stopPolling();
    timer.current = setInterval(() => {
      api
        .queueStatus()
        .then(applyQueue)
        .catch(() => {
          /* transient poll failure: keep waiting, next tick retries */
        });
    }, POLL_MS);
  }, [applyQueue, stopPolling]);

  // Restore queue state after reloads; load the player's online history.
  useEffect(() => {
    let cancelled = false;
    api
      .queueStatus()
      .then((body) => {
        if (cancelled) return;
        applyQueue(body);
        if (body.status === 'queued') startPolling();
      })
      .catch(() => undefined);
    api
      .listOnlineGames()
      .then((list) => {
        if (!cancelled) setGames(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load online games');
        }
      });
    return () => {
      cancelled = true;
      stopPolling();
      // Best-effort: leaving the page while queued must free the slot,
      // otherwise the next player is matched against an absent opponent.
      if (queuedRef.current) {
        queuedRef.current = false;
        void api.leaveQueue().catch(() => undefined);
      }
    };
  }, [applyQueue, startPolling, stopPolling]);

  async function handleJoin() {
    setBusy(true);
    setError(null);
    try {
      const body = await api.joinQueue();
      applyQueue(body);
      if (body.status === 'queued') startPolling();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to join the queue');
    } finally {
      setBusy(false);
    }
  }

  async function handleLeave() {
    setBusy(true);
    try {
      await api.leaveQueue();
    } catch {
      /* leaving is best-effort; local state resets either way */
    }
    stopPolling();
    queuedRef.current = false;
    setQueue({ status: 'idle' });
    setBusy(false);
  }

  const queued = queue.status === 'queued';

  return (
    <main id="main-content" className="lobby-page">
      <header className="welcome-band">
        <div>
          <h1>Play online</h1>
          <p>Queue up and we will pair you with the next player looking for a game.</p>
        </div>
      </header>

      {error && (
        <p role="alert" className="alert-error" style={{ marginBottom: 'var(--space-5)' }}>
          {error}
        </p>
      )}

      <Card>
        <div className="card-title">
          <h2>Matchmaking</h2>
          {queued && (
            <span className="badge badge-accent">
              <LoaderCircle size={13} aria-hidden="true" /> In queue
            </span>
          )}
        </div>
        {queued ? (
          <>
            <p role="status" className="loading-state">
              Waiting for an opponent…
            </p>
            <Button variant="ghost" onClick={() => void handleLeave()} disabled={busy}>
              <LogOut size={15} aria-hidden="true" />
              Leave queue
            </Button>
          </>
        ) : (
          <Button variant="primary" onClick={() => void handleJoin()} disabled={busy}>
            <Swords size={15} aria-hidden="true" />
            {busy ? 'Joining…' : 'Join the queue'}
          </Button>
        )}
      </Card>

      <Card className="span-full">
        <div className="card-title">
          <h2>Your online games</h2>
        </div>
        {games.length === 0 ? (
          <div className="empty-state">
            <h3>No online games yet</h3>
            <p>Join the queue and your first matched game will appear here.</p>
          </div>
        ) : (
          <ul className="game-list">
            {games.map((g) => (
              <li key={g.id}>
                <Link to={`/online/${g.id}`}>
                  <span className="game-id">Game #{g.id}</span>
                  <span className="game-mode">Online</span>
                  <span className="badge">{g.status === 'active' ? 'In progress' : g.status}</span>
                  <span className="game-moves">
                    {g.moves.length} {g.moves.length === 1 ? 'move' : 'moves'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <p style={{ marginTop: 'var(--space-4)' }}>
          <Link to="/" className="back-link">
            <Play size={13} aria-hidden="true" /> Back to dashboard
          </Link>
        </p>
      </Card>
    </main>
  );
}
