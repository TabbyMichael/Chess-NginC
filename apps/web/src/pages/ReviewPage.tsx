/**
 * Post-game review (REVIEW-003/004/006): every ply classified by Stockfish
 * (brilliant → blunder), the engine's suggested improvement, a coaching line,
 * the evaluation graph and a per-move board replay.
 *
 * Data comes from GET /games/:id/review when a review is stored, otherwise the
 * page triggers POST (one engine pass) and shows progress. The board is a
 * read-only replay: no move submission lives here.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Sparkles } from 'lucide-react';

import Chessboard from '../components/Chessboard';
import EvalGraph from '../components/EvalGraph';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useAchievementRide } from '../app/useAchievementRide';
import { ApiError, api } from '../lib/api-client';
import type { ReviewMoveResponse, ReviewResponse } from '../lib/api-types';
import { QUALITY_ORDER, formatEval, qualityMeta, uciSquares } from '../lib/review';

function QualityBadge({ quality }: { quality: string }) {
  const meta = qualityMeta(quality);
  return (
    <span className={`quality quality-${meta.css}`} title={meta.label}>
      <span aria-hidden="true">{meta.glyph || '•'}</span>
      <span className="sr-only">{meta.label}</span>
    </span>
  );
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const gameId = Number(id);
  const badId = !Number.isFinite(gameId) || gameId <= 0;

  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPly, setSelectedPly] = useState<number | null>(null);

  useEffect(() => {
    if (badId) return;
    let cancelled = false;
    // A stored review is served straight from the DB; 409 means "not analysed
    // yet", which triggers the single engine pass (REVIEW-001/005).
    const fetchOrGenerate = api
      .getGameReview(gameId)
      .catch((err: unknown) =>
        err instanceof ApiError && err.status === 409
          ? api.createGameReview(gameId)
          : Promise.reject(err),
      );
    fetchOrGenerate
      .then((data) => {
        if (cancelled) return;
        setReview(data);
        setSelectedPly(data.moves.length ? data.moves[data.moves.length - 1].ply : null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : 'Failed to load the review');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, badId]);

  const selected: ReviewMoveResponse | null = useMemo(() => {
    if (!review) return null;
    const found = review.moves.find((m) => m.ply === selectedPly);
    return found ?? review.moves[review.moves.length - 1] ?? null;
  }, [review, selectedPly]);

  // A finished analysis is a milestone of its own (reviews_completed).
  useAchievementRide(review);

  async function reanalyse() {
    setLoading(true);
    try {
      const data = await api.createGameReview(gameId, { force: true });
      setReview(data);
      setSelectedPly(data.moves.length ? data.moves[data.moves.length - 1].ply : null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to re-analyse');
    } finally {
      setLoading(false);
    }
  }

  if (badId) return <p role="alert">Invalid game id.</p>;

  if (loading) {
    return (
      <main id="main-content" className="review-page">
        <Card>
          <h1 className="card-title">Reviewing game…</h1>
          <p className="u-muted" role="status">
            Stockfish is replaying every move. Long games can take a minute.
          </p>
        </Card>
      </main>
    );
  }

  if (error) {
    return (
      <main id="main-content" className="review-page">
        <Card>
          <h1 className="card-title">Review unavailable</h1>
          <p role="alert">{error}</p>
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Back
          </Button>
        </Card>
      </main>
    );
  }

  if (!review) return null;

  if (review.status === 'failed') {
    return (
      <main id="main-content" className="review-page">
        <Card>
          <h1 className="card-title">The engine could not finish this review</h1>
          <p role="alert">{review.error ?? 'Analysis failed with an unknown error.'}</p>
          <div className="review-actions">
            <Button onClick={reanalyse}>
              <RefreshCw size={15} aria-hidden="true" />
              Try again
            </Button>
            <Button variant="ghost" onClick={() => navigate(-1)}>
              Back
            </Button>
          </div>
        </Card>
      </main>
    );
  }

  const hero = review.hero_color === 'w' ? 'White' : 'Black';
  // Online games are played under /online/:id; the linking page passes that
  // route through state so "back" lands where the player came from.
  const backTo =
    (location.state as { backTo?: string } | null)?.backTo ?? `/games/${review.game_id}`;
  const heroAccuracy = review.summary.accuracy?.[review.hero_color];
  const board = selected
    ? { fen: selected.pre_fen, last: uciSquares(selected.uci) }
    : { fen: null, last: null };
  const improvementsForHero = review.improvements.filter((i) => i.color === review.hero_color);

  return (
    <main id="main-content" className="review-page">
      <div className="review-header">
        <Link to={backTo} className="btn btn-ghost btn-small">
          <ArrowLeft size={14} aria-hidden="true" />
          Back to game
        </Link>
        <Button variant="ghost" onClick={reanalyse} disabled={loading}>
          <RefreshCw size={14} aria-hidden="true" />
          Re-analyse
        </Button>
      </div>

      <div className="review-grid">
        <section className="review-board-col" aria-label="review board">
          <Card>
            {board.fen ? (
              <Chessboard
                fen={board.fen}
                status="active"
                selected={null}
                onSelect={() => {}}
                onMove={() => {}}
                disabled
                lastMove={board.last}
              />
            ) : (
              <p className="u-muted">No moves to show.</p>
            )}
            {selected && (
              <p className="review-current-move">
                <QualityBadge quality={selected.quality} />
                <strong>
                  {selected.color === 'w' ? 'White' : 'Black'} played {selected.san}
                </strong>
                <span className="u-muted">
                  {formatEval(selected.eval_cp, selected.eval_mate)} · {selected.centipawn_loss} cp
                  off best
                </span>
                <span className="review-explanation">{selected.explanation}</span>
              </p>
            )}
          </Card>

          <Card>
            <h2 className="card-title">Evaluation over the game</h2>
            <EvalGraph
              points={review.eval_graph}
              activePly={selectedPly}
              onSelectPly={setSelectedPly}
            />
          </Card>
        </section>

        <section className="review-side-col" aria-label="review summary">
          <Card>
            <h2 className="card-title">
              {hero}&apos;s report card
              {typeof heroAccuracy === 'number' && (
                <span className="review-accuracy">{heroAccuracy}% accuracy</span>
              )}
            </h2>
            <ul className="quality-legend">
              {QUALITY_ORDER.map((q) => (
                <li key={q} className={`quality-row quality-${q}`}>
                  <QualityBadge quality={q} />
                  <span>{qualityMeta(q).label}</span>
                  <strong>{review.counts?.[q] ?? 0}</strong>
                </li>
              ))}
            </ul>
            <p className="u-muted">
              Depth {review.depth} · {review.summary.ply_count} plies analysed by {review.provider}
            </p>
          </Card>

          <Card>
            <h2 className="card-title">
              <Sparkles size={15} aria-hidden="true" /> Where to improve
            </h2>
            {improvementsForHero.length === 0 ? (
              <p className="u-muted">
                No mistakes or blunders — your moves matched the engine&rsquo;s plan.
              </p>
            ) : (
              <ol className="improvement-list">
                {improvementsForHero.map((imp) => (
                  <li key={imp.ply}>
                    <button
                      type="button"
                      className="improvement"
                      onClick={() => setSelectedPly(imp.ply)}
                    >
                      <span>
                        Move {imp.ply}: played <strong>{imp.san}</strong>
                      </span>
                      <span className="u-muted">
                        {imp.loss_cp} cp lost · better was {imp.best_uci}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          <Card>
            <h2 className="card-title">Move-by-move classification</h2>
            <ol className="review-move-list" aria-label="classified moves">
              {review.moves.map((move) => (
                <li key={move.ply}>
                  <button
                    type="button"
                    className={`review-move${move.ply === selectedPly ? ' active' : ''}`}
                    onClick={() => setSelectedPly(move.ply)}
                  >
                    <span className="review-move-number">{move.move_number}</span>
                    <QualityBadge quality={move.quality} />
                    <span className={`review-san side-${move.color}`}>{move.san}</span>
                    <span className="review-excerpt">{move.explanation}</span>
                  </button>
                </li>
              ))}
            </ol>
          </Card>
        </section>
      </div>
    </main>
  );
}
