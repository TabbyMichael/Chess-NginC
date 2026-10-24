/**
 * Coach assistant panel tests (Phase 11): asking a question, the moves it cites
 * walking the review tour, cross-game pattern recall, and the offline-friendly
 * error surface. The API is always mocked — nothing here reaches a real engine.
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps } from 'react';
import { describe, expect, it, vi } from 'vitest';

import CoachAssistant from './CoachAssistant';
import { ApiError, api } from '../lib/api-client';
import type { AssistantAnswerResponse, CoachPatternsResponse } from '../lib/api-types';

const ANSWER: AssistantAnswerResponse = {
  answer: 'Your c5 blunder hung a pawn; the engine preferred e5.',
  intent: 'explain',
  mode: 'deterministic',
  provider: 'stockfish+book',
  references: [
    { ply: 2, san: 'c5', color: 'b', note: 'hangs a pawn' },
    { ply: 4, san: 'Nf6', color: 'b', note: '' },
  ],
  position_fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
};

function renderPanel(overrides: Partial<ComponentProps<typeof CoachAssistant>> = {}) {
  const onSelectPly = vi.fn();
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(
    <CoachAssistant
      gameId={7}
      focusPly={2}
      onSelectPly={onSelectPly}
      onClose={onClose}
      {...overrides}
    />,
  );
  return { user, onSelectPly, onClose };
}

describe('CoachAssistant asking', () => {
  it('sends the question with the current focus and renders the grounded answer', async () => {
    const ask = vi.spyOn(api, 'askCoach').mockResolvedValue(ANSWER);
    const { user, onSelectPly } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'what went wrong?');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByText(ANSWER.answer)).toBeInTheDocument();
    expect(ask).toHaveBeenCalledWith(7, { question: 'what went wrong?', focus_ply: 2 });

    // Your question is echoed in the thread.
    expect(screen.getByText('what went wrong?')).toBeInTheDocument();

    // Clicking a cited move walks the review tour to that ply.
    const refs = screen.getByRole('list', { name: 'moves this answer cites' });
    await user.click(within(refs).getByText('c5'));
    expect(onSelectPly).toHaveBeenCalledWith(2);
  });

  it('disables Ask until a question is typed', () => {
    renderPanel();
    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  });

  it('surfaces an API error without leaving the panel blank', async () => {
    vi.spyOn(api, 'askCoach').mockRejectedValue(new ApiError(429, 'Slow down a moment.'));
    const { user } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'hi');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Slow down a moment.');
  });
});

describe('CoachAssistant cross-game patterns', () => {
  it('loads and lists the openings where the player errs most', async () => {
    const res: CoachPatternsResponse = {
      summary: 'Most of your errors come in the Sicilian Defense.',
      items: [
        {
          opening_family: 'Sicilian Defense',
          mistakes: 1,
          blunders: 2,
          total_errors: 3,
          avg_loss_cp: 180,
        },
      ],
    };
    const patterns = vi.spyOn(api, 'coachPatterns').mockResolvedValue(res);
    const { user } = renderPanel();

    await user.click(screen.getByRole('button', { name: 'Show patterns' }));

    expect(patterns).toHaveBeenCalledWith(7);
    const panel = await screen.findByLabelText('cross-game patterns');
    expect(within(panel).getByText('Sicilian Defense')).toBeInTheDocument();
    expect(within(panel).getByText('2 blunders · 1 mistake · avg 180 cp')).toBeInTheDocument();
  });
});

describe('CoachAssistant closing', () => {
  it('calls onClose when the close button is pressed', async () => {
    const { user, onClose } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Close coach' }));
    expect(onClose).toHaveBeenCalled();
  });
});
