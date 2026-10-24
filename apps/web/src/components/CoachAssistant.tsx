/**
 * Coach assistant panel (Phase 11): a conversational read of the reviewed game,
 * opened from the ⭐ next to "Where to improve".
 *
 * Everything it shows is grounded — the answer text, the moves it cites and the
 * board position it returns all come from engine + book facts about *this* game
 * (or the player's own indexed games for cross-game patterns). Clicking a cited
 * move walks the review tour to that ply, so the coach and the board stay in sync.
 *
 * The panel is dumb: it owns only its question box and the running thread, and
 * talks to the API through the shared client. A 429/error is surfaced inline so
 * the surrounding review never disappears because the coach had nothing to say.
 */
import { useCallback, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Lightbulb, Loader2, Send, X } from 'lucide-react';

import { Button } from './ui/Button';
import { ApiError, api } from '../lib/api-client';
import type { AssistantAnswerResponse, CoachPattern } from '../lib/api-types';

type Props = {
  gameId: number;
  /** Ply the review cursor sits on; the coach resolves focus from it. */
  focusPly: number | null;
  /** Walk the review tour to a ply when a cited move is clicked. */
  onSelectPly: (ply: number) => void;
  onClose: () => void;
};

type Turn = {
  id: number;
  role: 'you' | 'coach';
  text: string;
  answer?: AssistantAnswerResponse;
};

/** Short, human labels for the coach's detected intent. */
const INTENT_LABEL: Record<string, string> = {
  summary: 'Overview',
  plan: 'Best way to proceed',
  alternatives: 'Other ways it could have gone',
  position: 'The position',
  explain: 'Why that move',
  patterns: 'Across your games',
  opening: 'Opening theory',
  general: 'Coach',
};

export default function CoachAssistant({ gameId, focusPly, onSelectPly, onClose }: Props) {
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [patterns, setPatterns] = useState<CoachPattern[] | null>(null);
  const [patternSummary, setPatternSummary] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextId = useRef(1);

  const push = useCallback((turn: Omit<Turn, 'id'>) => {
    setTurns((prev) => [...prev, { ...turn, id: nextId.current++ }]);
  }, []);

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion('');
    setError(null);
    setBusy(true);
    push({ role: 'you', text });
    try {
      const answer = await api.askCoach(gameId, { question: text, focus_ply: focusPly ?? null });
      push({ role: 'coach', text: answer.answer, answer });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The coach could not answer just now.');
    } finally {
      setBusy(false);
    }
  }

  async function loadPatterns() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const res = await api.coachPatterns(gameId);
      setPatterns(res.items);
      setPatternSummary(res.summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No cross-game patterns to show yet.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="coach-panel" aria-label="coach assistant">
      <header className="coach-head">
        <h2 className="card-title">Coach assistant</h2>
        <Button variant="ghost" className="coach-close" onClick={onClose} aria-label="Close coach">
          <X size={15} aria-hidden="true" />
        </Button>
      </header>

      <div className="coach-thread">
        {turns.length === 0 && !patterns && (
          <p className="u-muted">
            Ask about this game — the positions, the best way to proceed, or how it could have gone
            differently. Answers are drawn only from the engine analysis of your own moves.
          </p>
        )}
        {turns.map((turn) =>
          turn.role === 'you' ? (
            <p key={turn.id} className="coach-turn coach-you">
              {turn.text}
            </p>
          ) : (
            <div key={turn.id} className="coach-turn coach-answer">
              <p className="coach-intent">
                {INTENT_LABEL[turn.answer?.intent ?? ''] ?? 'Coach'}
                {turn.answer?.mode === 'llm' ? ' · phrased by a model, cited from your game' : ''}
              </p>
              <p className="coach-text">{turn.text}</p>
              {turn.answer?.position_fen && (
                <button
                  type="button"
                  className="coach-board-link"
                  onClick={() => onSelectPly(turn.answer?.references?.[0]?.ply ?? focusPly ?? 0)}
                >
                  Show the position on the board
                </button>
              )}
              {turn.answer && turn.answer.references.length > 0 && (
                <ul className="coach-refs" aria-label="moves this answer cites">
                  {turn.answer.references.map((ref) => (
                    <li key={`${turn.id}-${ref.ply}`}>
                      <button
                        type="button"
                        className="coach-ref"
                        onClick={() => onSelectPly(ref.ply)}
                        title={ref.note || undefined}
                      >
                        <span className={`review-san side-${ref.color}`}>{ref.san}</span>
                        <span className="u-muted">move {ref.ply}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        )}
      </div>

      {patterns && (
        <div className="coach-patterns" aria-label="cross-game patterns">
          <h3 className="coach-patterns-title">Where you slip most</h3>
          {patternSummary && <p className="u-muted">{patternSummary}</p>}
          {patterns.length === 0 ? (
            <p className="u-muted">No repeated errors found across your reviewed games yet.</p>
          ) : (
            <ul aria-label="error counts by opening">
              {patterns.map((p) => (
                <li key={p.opening_family} className="coach-pattern">
                  <strong>{p.opening_family}</strong>
                  <span className="u-muted">
                    {p.blunders} blunder{p.blunders === 1 ? '' : 's'} · {p.mistakes} mistake
                    {p.mistakes === 1 ? '' : 's'} · avg {p.avg_loss_cp} cp
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && <p role="alert">{error}</p>}

      <form className="coach-ask" onSubmit={ask}>
        <label className="sr-only" htmlFor="coach-question">
          Ask the coach about this game
        </label>
        <input
          id="coach-question"
          className="coach-input"
          type="text"
          maxLength={400}
          value={question}
          placeholder="e.g. What was my worst move and why?"
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        <Button type="submit" aria-label="Send question" disabled={busy || question.trim() === ''}>
          {busy ? (
            <Loader2 size={15} className="spin" aria-hidden="true" />
          ) : (
            <Send size={15} aria-hidden="true" />
          )}
          Ask
        </Button>
        <Button
          variant="ghost"
          type="button"
          aria-label="Show patterns"
          onClick={loadPatterns}
          disabled={busy}
        >
          <Lightbulb size={15} aria-hidden="true" />
          Patterns
        </Button>
      </form>
    </section>
  );
}
