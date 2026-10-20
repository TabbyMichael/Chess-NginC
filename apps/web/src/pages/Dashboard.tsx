/**
 * Dashboard (WEB-009/020/021/022/023): new-game setup (mode + difficulty),
 * saved-game listing, logout (WEB-007).
 * Gen Alpha makeover: vibrant game lobby, quick start, XP display, badges.
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';

import { useAuth } from '../app/useAuth';
import { ApiError, api } from '../lib/api-client';
import type { GameMode, GameResponse } from '../lib/api-types';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { XPBar } from '../components/ui/XPBar';

const MODE_LABELS: Record<GameMode, string> = {
  local: 'Local Two-Player',
  computer: 'Player vs Computer',
};

const MODE_META: Record<GameMode, { emoji: string; desc: string }> = {
  computer: { emoji: '🤖', desc: 'Battle the engine' },
  local: { emoji: '👥', desc: 'Pass & play with a friend' },
};

const DIFFICULTY_META: Record<number, { label: string; emoji: string; blurb: string }> = {
  1: { label: 'Easy', emoji: '🌱', blurb: 'Chill vibes' },
  3: { label: 'Medium', emoji: '🔥', blurb: 'Spicy' },
  5: { label: 'Hard', emoji: '👹', blurb: 'No mercy' },
};

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [games, setGames] = useState<GameResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<GameMode>('computer');
  const [depth, setDepth] = useState(3);
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

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <main className="flex-1 w-full max-w-5xl px-4 py-6">
      <motion.header
        className="hero-card mb-2xl"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <span className="hero-kicker">⚡ Season 1 · live now</span>
        <h1 className="hero-title">Chess NginC</h1>
        <p className="hero-sub">
          Outsmart the bot, stack wins, flex badges. Your arena awaits.
        </p>
        <div className="quick-start-actions">
          <Button variant="primary" onClick={handleCreate} disabled={creating}>
            {creating ? 'Summoning board…' : '▶ Quick play'}
          </Button>
          <Button variant="ghost" onClick={handleLogout}>
            Log out
          </Button>
        </div>
        <div className="stat-row" aria-label="player stats">
          <span className="stat-chip">🏆 <b>{games.filter((g) => g.status === 'checkmate').length}</b> dubs</span>
          <span className="stat-chip">🎮 <b>{games.length}</b> games</span>
          <span className="stat-chip">🔥 <b>{games.length > 0 ? games[games.length - 1].moves.length : 0}</b> moves last game</span>
        </div>
      </motion.header>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="mb-xl"
      >
        <XPBar level={5} xp={750} maxXp={1000} />
      </motion.div>

      <div className="dashboard-grid">
        <Card>
          <h2 className="text-xl font-bold mb-md">New game · 🎯 new battle</h2>
          <p className="u-text-sm mb-lg">Pick your mode + bot difficulty</p>
          <div className="mode-grid" role="radiogroup" aria-label="Game mode">
            {(Object.keys(MODE_LABELS) as GameMode[]).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                className={`mode-card ${mode === value ? 'active' : ''}`}
                onClick={() => setMode(value)}
              >
                <span className="mode-emoji" aria-hidden="true">{MODE_META[value].emoji}</span>
                <span className="mode-name">{MODE_LABELS[value]}</span>
                <span className="mode-desc">{MODE_META[value].desc}</span>
              </button>
            ))}
          </div>
          {/* Hidden select keeps old a11y/tests contract if anything queries a select; visual picker above is primary. */}
          <label className="label" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
            Game Mode
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as GameMode)}
              tabIndex={-1}
              aria-hidden="true"
            >
              {Object.entries(MODE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {mode === 'computer' && (
            <>
              <p className="label">Bot difficulty</p>
              <div className="diff-grid" role="radiogroup" aria-label="Engine difficulty">
                {Object.entries(DIFFICULTY_META).map(([value, meta]) => (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={depth === Number(value)}
                    className={`diff-card ${depth === Number(value) ? 'active' : ''}`}
                    onClick={() => setDepth(Number(value))}
                  >
                    {meta.emoji} {meta.label}
                    <small>{meta.blurb} · depth {value}</small>
                  </button>
                ))}
              </div>
              <label className="label" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
                Engine Difficulty
                <select
                  value={depth}
                  onChange={(e) => setDepth(Number(e.target.value))}
                  tabIndex={-1}
                  aria-hidden="true"
                >
                  {Object.entries(DIFFICULTY_META).map(([value, meta]) => (
                    <option key={value} value={value}>
                      {meta.label} (depth {value})
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <Button
            variant="brand"
            onClick={handleCreate}
            disabled={creating}
            className="w-full"
          >
            {creating ? 'Creating…' : `⚔ Start ${mode === 'computer' ? DIFFICULTY_META[depth].label : 'local'} battle`}
          </Button>
        </Card>

        <Card>
          <h2 className="text-xl font-bold mb-md">Your Games</h2>
          {loading && <p role="status" className="text-center text-ink-soft">Loading games…</p>}
          {error && (
            <p role="alert" className="error text-center">
              {error}
            </p>
          )}
          {!loading && !error && games.length === 0 && (
            <div className="empty-state">
              <p>No games yet — start one above.</p>
            </div>
          )}
          {!loading && !error && games.length > 0 && (
            <ul className="game-list">
              {games.map((g) => (
                <li key={g.id} className="game-item">
                  <Link to={`/games/${g.id}`} className="flex items-center gap-md">
                    <span className="font-mono text-neon-pink">Game #{g.id}</span>
                    <span className="text-ink-soft text-sm">{MODE_LABELS[g.mode]}</span>
                    <span className="text-ink-soft text-sm">• {g.status}</span>
                    <span className="ml-auto text-neon-green font-bold">{g.moves.length} moves</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className="text-xl font-bold mb-md">Achievements</h2>
          <div className="badge-grid">
            <Badge name="First Move" desc="Play your first game" icon="♟️" unlocked={true} />
            <Badge name="Checkmate King" desc="Win by checkmate" icon="👑" unlocked={true} />
            <Badge name="Speed Demon" desc="Win in under 2 minutes" icon="⚡" unlocked={false} />
            <Badge name="Comeback Kid" desc="Win from behind" icon="🔄" unlocked={false} />
          </div>
        </Card>
      </div>
    </main>
  );
}
