/**
 * Dashboard (WEB-009/020/021/022/023): new-game setup (mode + difficulty),
 * saved-game listing, player statistics and achievements.
 * Game statistics are derived from the listed games; the achievement strip is
 * the server's own catalog progress (GET /me/achievements), so nothing here is
 * guessed from the client's point of view.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Coins, Cpu, Play, Users } from 'lucide-react';

import { useAuth } from '../app/useAuth';
import { ApiError, api } from '../lib/api-client';
import type { AchievementListResponse, GameMode, GameResponse, GameStatus } from '../lib/api-types';
import { TIER_LABELS, formatCounter, newestUnlocked, sortForGallery } from '../lib/achievements';
import { GROUP_ICONS, DEFAULT_GROUP_ICON } from '../lib/achievement-icons';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

const MODE_LABELS: Record<GameMode, string> = {
  local: 'Two players',
  computer: 'vs Computer',
  online: 'Online match',
};

const MODE_DESCRIPTIONS: Record<GameMode, string> = {
  local: 'Pass and play on one board',
  computer: 'Battle the Stockfish engine',
  online: 'Get matched against another player',
};

const DIFFICULTIES = [
  { depth: 1, label: 'Easy' },
  { depth: 3, label: 'Medium' },
  { depth: 5, label: 'Hard' },
] as const;

const PREVIEW_LIMIT = 6;

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
  const [achievements, setAchievements] = useState<AchievementListResponse | null>(null);
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

  // The achievement strip is decorative next to the board list, so a failure
  // here only hides the strip; the gallery page reports its own errors.
  useEffect(() => {
    let cancelled = false;
    api
      .listAchievements()
      .then((result) => {
        if (!cancelled) setAchievements(result);
      })
      .catch(() => undefined);
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
    };
  }, [games]);

  async function handleCreate() {
    // Online games come from the lobby queue, never from POST /games.
    if (mode === 'online') {
      navigate('/lobby');
      return;
    }
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

  const recentUnlocks = useMemo(
    () => (achievements ? newestUnlocked(achievements.items, PREVIEW_LIMIT) : []),
    [achievements],
  );
  // Players with no unlocks yet still want to see what is closest. If the
  // whole catalog reads zero, the strip stays empty rather than posturing.
  const closest = useMemo(() => {
    if (!achievements || recentUnlocks.length > 0) return [];
    return sortForGallery(achievements.items.filter((item) => !item.unlocked)).slice(
      0,
      PREVIEW_LIMIT,
    );
  }, [achievements, recentUnlocks]);
  const tiles = recentUnlocks.length > 0 ? recentUnlocks : closest;

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
                : mode === 'online'
                  ? 'Go to the lobby'
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
                    <Link to={g.mode === 'online' ? `/online/${g.id}` : `/games/${g.id}`}>
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
            <span className="u-text-xs u-muted">
              {achievements
                ? `${achievements.unlocked} of ${achievements.total} unlocked`
                : 'Earned by playing'}
            </span>
          </div>
          {tiles.length > 0 ? (
            <div className="achievement-grid">
              {tiles.map((item) => {
                // Map lookup keeps the glyph identity stable across re-renders.
                const Icon = GROUP_ICONS[item.group] ?? DEFAULT_GROUP_ICON;
                return (
                  <Badge
                    key={item.key}
                    name={item.title}
                    desc={item.description}
                    icon={<Icon size={18} />}
                    unlocked={item.unlocked}
                    className={`tier-${item.tier}`}
                    progress={item.unlocked ? 1 : item.progress}
                    detail={
                      item.unlocked
                        ? (TIER_LABELS[item.tier] ?? item.tier)
                        : formatCounter(item.value, item.threshold)
                    }
                  />
                );
              })}
            </div>
          ) : (
            <p className="hint">
              {achievements
                ? 'Nothing earned yet — play a move and the first tiles unlock instantly.'
                : 'Achievement progress is unavailable right now.'}
            </p>
          )}
          <p className="achievement-preview-link">
            <Link to="/achievements">
              {recentUnlocks.length > 0 ? 'All achievements' : 'Open the achievement gallery'}
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </p>
        </Card>
      </div>
    </main>
  );
}
