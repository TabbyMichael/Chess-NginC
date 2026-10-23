/**
 * Dashboard (WEB-009/020/021/022/023): new-game setup (mode + difficulty),
 * saved-game listing, player statistics and achievements.
 * All stats and achievement states are derived from real game data — nothing
 * is invented; metrics that the API cannot support are omitted.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { Clock, Coins, Cpu, Crown, Flag, Play, Trophy, Users } from 'lucide-react';

import { useAuth } from '../app/useAuth';
import { ApiError, api } from '../lib/api-client';
import type { GameMode, GameResponse, GameStatus } from '../lib/api-types';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

const MODE_LABELS: Record<GameMode, string> = {
  local: 'Two players',
  computer: 'vs Computer',
};

const MODE_DESCRIPTIONS: Record<GameMode, string> = {
  local: 'Pass and play on one board',
  computer: 'Battle the Stockfish engine',
};

const DIFFICULTIES = [
  { depth: 1, label: 'Easy' },
  { depth: 3, label: 'Medium' },
  { depth: 5, label: 'Hard' },
] as const;

const STATUS_META: Record<GameStatus, { label: string; badge: string }> = {
  active: { label: 'In progress', badge: 'badge badge-accent' },
  checkmate: { label: 'Checkmate', badge: 'badge' },
  stalemate: { label: 'Stalemate', badge: 'badge badge-warning' },
  draw: { label: 'Draw', badge: 'badge badge-warning' },
  resigned: { label: 'Resigned', badge: 'badge badge-danger' },
  abandoned: { label: 'Abandoned', badge: 'badge' },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [games, setGames] = useState<GameResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<GameMode>('computer');
  const [depth, setDepth] = useState<number>(3);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .listGames()
      .then((list) => {
        if (!cancelled) setGames(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load games');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const count = (status: GameStatus) => games.filter((g) => g.status === status).length;
    return {
      total: games.length,
      active: count('active'),
      checkmates: count('checkmate'),
      draws: count('draw') + count('stalemate'),
      resigned: count('resigned'),
      moves: games.reduce((sum, g) => sum + g.moves.length, 0),
      longest: games.reduce((max, g) => Math.max(max, g.moves.length), 0),
    };
  }, [games]);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const game = await api.createGame({ mode });
      navigate(`/games/${game.id}`, { state: { depth } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create game');
    } finally {
      setCreating(false);
    }
  }

  const difficultyLabel = DIFFICULTIES.find((d) => d.depth === depth)?.label ?? '';

  return (
    <main id="main-content">
      <section className="welcome-band" aria-label="welcome">
        <div>
          <h1>Your chess arena</h1>
          <p>Pick a mode, choose your difficulty, and get to a board in one click.</p>
        </div>
        <Button variant="primary" onClick={handleCreate} disabled={creating}>
          <Play size={15} aria-hidden="true" />
          {creating ? 'Starting…' : 'Play chess'}
        </Button>
      </section>

      {error && (
        <p role="alert" className="alert-error" style={{ marginBottom: 'var(--space-5)' }}>
          {error}
        </p>
      )}

      <section className="stats-grid" aria-label="player statistics">
        <div className="stat">
          <span className="stat-value">{user ? user.points.toLocaleString() : '—'}</span>
          <span className="stat-label">
            <Coins size={13} aria-hidden="true" /> Points
          </span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.total}</span>
          <span className="stat-label">Games</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.active}</span>
          <span className="stat-label">In progress</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.checkmates}</span>
          <span className="stat-label">Checkmates</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.draws}</span>
          <span className="stat-label">Draws</span>
        </div>
        <div className="stat">
          <span className="stat-value">{stats.moves}</span>
          <span className="stat-label">Moves played</span>
        </div>
      </section>

      <div className="dashboard-grid">
        <Card>
          <div className="card-title">
            <h2>New game</h2>
          </div>
          <p className="choice-label">Mode</p>
          <div className="option-grid" role="radiogroup" aria-label="Game mode">
            {(Object.keys(MODE_LABELS) as GameMode[]).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                className={`option-card${mode === value ? ' selected' : ''}`}
                onClick={() => setMode(value)}
              >
                <span className="option-name">
                  {value === 'computer' ? (
                    <Cpu size={15} aria-hidden="true" />
                  ) : (
                    <Users size={15} aria-hidden="true" />
                  )}
                  {MODE_LABELS[value]}
                </span>
                <span className="option-desc">{MODE_DESCRIPTIONS[value]}</span>
              </button>
            ))}
          </div>
          {mode === 'computer' && (
            <>
              <p className="choice-label">Bot difficulty</p>
              <div className="option-grid diff" role="radiogroup" aria-label="Engine difficulty">
                {DIFFICULTIES.map(({ depth: d, label }) => (
                  <button
                    key={d}
                    type="button"
                    role="radio"
                    aria-checked={depth === d}
                    className={`option-card${depth === d ? ' selected' : ''}`}
                    onClick={() => setDepth(d)}
                  >
                    <span className="option-name">{label}</span>
                    <span className="option-desc">depth {d}</span>
                  </button>
                ))}
              </div>
            </>
          )}
          <Button variant="primary" onClick={handleCreate} disabled={creating} className="w-full">
            {creating
              ? 'Creating…'
              : mode === 'computer'
                ? `Start game vs Computer (${difficultyLabel})`
                : 'Start two-player game'}
          </Button>
        </Card>

        <Card>
          <div className="card-title">
            <h2>Your Games</h2>
            {stats.total > 0 && <span className="badge">{stats.total} total</span>}
          </div>
          {loading && (
            <p role="status" className="loading-state">
              Loading games…
            </p>
          )}
          {!loading && !error && games.length === 0 && (
            <div className="empty-state">
              <h3>No games yet</h3>
              <p>Start your first game from the panel beside this one.</p>
            </div>
          )}
          {!loading && !error && games.length > 0 && (
            <ul className="game-list">
              {games.map((g) => {
                const status = STATUS_META[g.status as GameStatus] ?? STATUS_META.active;
                return (
                  <li key={g.id}>
                    <Link to={`/games/${g.id}`}>
                      <span className="game-id">Game #{g.id}</span>
                      <span className="game-mode">{MODE_LABELS[g.mode]}</span>
                      <span className={status.badge}>{status.label}</span>
                      <span className="game-moves">
                        {g.moves.length} {g.moves.length === 1 ? 'move' : 'moves'}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="span-full">
          <div className="card-title">
            <h2>Achievements</h2>
            <span className="u-text-xs u-muted">Earned from your saved games</span>
          </div>
          <div className="achievement-grid">
            <Badge
              name="First Move"
              desc="Play your first move"
              icon={<Flag size={18} />}
              unlocked={stats.moves > 0}
            />
            <Badge
              name="Checkmate King"
              desc="Finish a game by checkmate"
              icon={<Crown size={18} />}
              unlocked={stats.checkmates > 0}
            />
            <Badge
              name="Regular"
              desc="Play three or more games"
              icon={<Trophy size={18} />}
              unlocked={stats.total >= 3}
            />
            <Badge
              name="Endurance"
              desc="Reach 40+ moves in one game"
              icon={<Clock size={18} />}
              unlocked={stats.longest >= 40}
            />
          </div>
        </Card>
      </div>
    </main>
  );
}
