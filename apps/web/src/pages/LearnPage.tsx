/**
 * Learn (LEARN-002/003/004/005): themed skill cards, an interactive drill
 * board, and puzzles mined from the player's own analysed games.
 *
 * The page renders positions and captures a move, but it never decides whether
 * an answer is correct — the verdict, the answer reveal and the points all come
 * from the server (architecture rule: the frontend does not determine
 * outcomes). The puzzle payload is deliberately answer-free; the answer only
 * appears in the attempt response, after the player has tried.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { GraduationCap, RotateCcw, Sparkles } from 'lucide-react';

import Chessboard from '../components/Chessboard';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useAchievementRide } from '../app/useAchievementRide';
import { ApiError, api } from '../lib/api-client';
import type {
  MinePuzzleResponse,
  PuzzleResponse,
  TrainingAttemptResponse,
  TrainingSummaryResponse,
} from '../lib/api-types';
import { isCheck } from '../lib/chess';
import { levelChip, themeIdea, themeOrder, uciFromTo } from '../lib/training';

export default function LearnPage() {
  const [summary, setSummary] = useState<TrainingSummaryResponse | null>(null);
  const [mine, setMine] = useState<MinePuzzleResponse[]>([]);
  const [puzzle, setPuzzle] = useState<PuzzleResponse | null>(null);
  const [result, setResult] = useState<TrainingAttemptResponse | null>(null);
  // The board is parent-controlled: it needs a selected square to preview moves.
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Progress + own-game list, refreshed after any attempt so the cards move.
  const refresh = useCallback(async () => {
    const [summaryData, mineData] = await Promise.all([api.trainingSummary(), api.trainingMine()]);
    setSummary(summaryData);
    setMine(mineData);
  }, []);

  useEffect(() => {
    let cancelled = false;
    // The initial load fetches directly and only sets state in the promise
    // callbacks — never synchronously in the effect body.
    Promise.all([api.trainingSummary(), api.trainingMine()])
      .then(([summaryData, mineData]) => {
        if (cancelled) return;
        setSummary(summaryData);
        setMine(mineData);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load training');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function openPuzzle(theme?: string, source?: string) {
    setBusy(true);
    setError(null);
    try {
      const data = await api.trainingPuzzle(theme, source);
      setPuzzle(data);
      setResult(null);
      setSelected(null);
    } catch (err) {
      // 404 is a real answer here: everything in that theme is already solved.
      setError(err instanceof ApiError ? err.message : 'Could not load a puzzle');
      setPuzzle(null);
    } finally {
      setBusy(false);
    }
  }

  async function submit(uci: string, reveal = false) {
    if (!puzzle) return;
    setBusy(true);
    try {
      const data = await api.submitTrainingAttempt({ key: puzzle.key, uci, reveal });
      setResult(data);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record the attempt');
    } finally {
      setBusy(false);
    }
  }

  // Achievements unlocked by a solve ride the attempt response (ACH-006).
  useAchievementRide(result);

  const orderedThemes = useMemo(() => (summary ? themeOrder(summary.themes) : []), [summary]);

  if (loading) {
    return (
      <main id="main-content" className="learn-page">
        <Card>
          <p role="status">Loading your training…</p>
        </Card>
      </main>
    );
  }

  return (
    <main id="main-content" className="learn-page">
      <header className="learn-header">
        <h1>
          <GraduationCap size={20} aria-hidden="true" /> Learn the patterns
        </h1>
        {summary && (
          <p className="u-muted">
            {summary.puzzles_solved} puzzles solved · {summary.streak} in a row ·{' '}
            {summary.mine_available} missed moves to drill
          </p>
        )}
      </header>

      {error && <p role="alert">{error}</p>}

      <section className="learn-grid" aria-label="skill areas">
        {orderedThemes.map((theme) => {
          const progress = summary?.themes[theme];
          if (!progress) return null;
          const pct = Math.round(progress.pct * 100);
          return (
            <Card key={theme} className="skill-card">
              <h2 className="card-title">{progress.label}</h2>
              <p className="u-muted">{themeIdea(theme)}</p>
              <p className="skill-count">
                {progress.solved}/{progress.attempts} solved
                <span className="badge">{levelChip(progress.level)}</span>
              </p>
              <div className="progress-bar" role="img" aria-label={`${pct}% of drills solved`}>
                <span className="progress-fill" style={{ width: `${pct}%` }} />
              </div>
              <Button variant="ghost" onClick={() => openPuzzle(theme)} disabled={busy}>
                Practise this
              </Button>
            </Card>
          );
        })}
      </section>

      {puzzle && (
        <Card className="drill-panel">
          <div className="drill-board">
            <Chessboard
              fen={puzzle.fen}
              status="active"
              selected={selected}
              onSelect={setSelected}
              onMove={(from, to, promotion) => submit(`${from}${to}${promotion ?? ''}`)}
              disabled={busy || result !== null}
              lastMove={result ? uciFromTo(`${result.solution_from}${result.solution_to}`) : null}
              inCheck={isCheck(puzzle.fen)}
            />
          </div>
          <div className="drill-side">
            <p className="drill-prompt">{puzzle.prompt}</p>
            {result ? (
              <>
                <p className={`drill-banner${result.solved ? ' solved' : ''}`} role="status">
                  {result.solved
                    ? `Solved! +${result.points_awarded} points`
                    : 'Not this drill’s move.'}
                </p>
                <p className="drill-answer">
                  <strong>{result.solution_san}</strong>
                  {result.why && <span className="u-muted"> {result.why}</span>}
                </p>
                {result.continuation.length > 0 && (
                  <p className="u-muted">Line: {result.continuation.join(' ')}</p>
                )}
                <div className="drill-actions">
                  <Button onClick={() => openPuzzle(puzzle.theme)} disabled={busy}>
                    Next puzzle
                  </Button>
                </div>
              </>
            ) : (
              <div className="drill-actions">
                <Button variant="ghost" onClick={() => submit('', true)} disabled={busy}>
                  <Sparkles size={14} aria-hidden="true" /> Show me
                </Button>
              </div>
            )}
          </div>
        </Card>
      )}

      <section className="mine-strip" aria-label="from your own games">
        <Card>
          <h2 className="card-title">
            <RotateCcw size={15} aria-hidden="true" /> From your own games
          </h2>
          {summary && summary.mine_available > 0 ? (
            <>
              <p className="u-muted">
                {summary.mine_available} moves you missed, taken from games you analysed.
              </p>
              <Button onClick={() => openPuzzle(undefined, 'game')} disabled={busy}>
                Drill a missed move
              </Button>
            </>
          ) : (
            <p className="u-muted">
              Analyse a finished game to turn your own blunders into drills.
            </p>
          )}
          <ul className="mine-list">
            {mine.map((p) => (
              <li key={p.key}>
                <button
                  type="button"
                  className="mine-item"
                  onClick={() => openPuzzle(undefined, 'game')}
                >
                  <span>{p.prompt}</span>
                  <Link to={`/games/${p.game_id}/review`} onClick={(e) => e.stopPropagation()}>
                    View game
                  </Link>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </section>
    </main>
  );
}
