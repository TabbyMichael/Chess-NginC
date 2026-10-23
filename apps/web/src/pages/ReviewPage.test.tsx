/**
 * Review-page tests: cached-vs-generated review loading, classification
 * rendering, board replay on move click, and the improvement shortcuts
 * (REVIEW-003/004/006).
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../app/AuthContext';
import { ApiError, api } from '../lib/api-client';
import type { ReviewResponse } from '../lib/api-types';
import ReviewPage from './ReviewPage';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';

function review(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    id: 3,
    game_id: 7,
    status: 'completed',
    provider: 'stockfish',
    depth: 15,
    hero_color: 'w',
    error: null,
    summary: { ply_count: 2, accuracy: { w: 92, b: 71 } },
    counts: { best: 1, excellent: 0, good: 1, inaccuracy: 0, mistake: 0, blunder: 0, brilliant: 0 },
    moves: [
      {
        ply: 1,
        move_number: 1,
        uci: 'e2e4',
        san: 'e4',
        pre_fen: START_FEN,
        color: 'w',
        quality: 'best',
        centipawn_loss: 0,
        best_uci: 'e2e4',
        eval_cp: 20,
        eval_mate: null,
        explanation: 'e4 is exactly what the engine wants. Well played.',
      },
      {
        ply: 2,
        move_number: 1,
        uci: 'e7e5',
        san: 'e5',
        pre_fen: AFTER_E4,
        color: 'b',
        quality: 'good',
        centipawn_loss: 25,
        best_uci: 'c7c5',
        eval_cp: -20,
        eval_mate: null,
        explanation: 'e5 is solid, just 25 cp under the best line.',
      },
    ],
    eval_graph: [
      { ply: 1, cp: 20, mate: null },
      { ply: 2, cp: -20, mate: null },
    ],
    improvements: [
      { ply: 2, san: 'e5', color: 'b', best_uci: 'c7c5', loss_cp: 25 },
      { ply: 4, san: 'Nf6', color: 'w', best_uci: 'd2d4', loss_cp: 210 },
    ],
    ...overrides,
  };
}

function renderReview(path = '/games/7/review') {
  const user = userEvent.setup();
  vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/games/:id/review" element={<ReviewPage />} />
          <Route path="/games/:id" element={<p>Game page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('ReviewPage loading (REVIEW-001/005)', () => {
  it('serves a stored review without re-analysing', async () => {
    const get = vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const create = vi.spyOn(api, 'createGameReview');
    renderReview();

    expect(await screen.findByText(/report card/)).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith(7);
    expect(create).not.toHaveBeenCalled();
  });

  it('generates one when none exists yet (409 from the cache read)', async () => {
    vi.spyOn(api, 'getGameReview').mockRejectedValue(new ApiError(409, 'No review exists yet'));
    const create = vi.spyOn(api, 'createGameReview').mockResolvedValue(review());
    renderReview();

    expect(
      await screen.findByText('e4 is exactly what the engine wants. Well played.'),
    ).toBeInTheDocument();
    expect(create).toHaveBeenCalledWith(7);
  });

  it('surfaces a failed analysis instead of an empty board', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(
      review({ status: 'failed', error: 'Stockfish binary not found', moves: [], eval_graph: [] }),
    );
    renderReview();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Stockfish binary not found');
  });

  it('rejects a non-numeric game id without fetching', async () => {
    const get = vi.spyOn(api, 'getGameReview');
    renderReview('/games/abc/review');
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid game id.');
    expect(get).not.toHaveBeenCalled();
  });
});

describe('ReviewPage content (REVIEW-003/004)', () => {
  it('lists every ply with its grade and coaching line', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    const list = await screen.findByRole('list', { name: 'classified moves' });
    expect(within(list).getAllByRole('button')).toHaveLength(2);
    expect(within(list).getByText('★')).toBeInTheDocument(); // the 'best' glyph
    expect(
      within(list).getByText('e5 is solid, just 25 cp under the best line.'),
    ).toBeInTheDocument();
  });

  it('jumps the board to the clicked ply', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    const list = await screen.findByRole('list', { name: 'classified moves' });
    const pawnOnE4 = () => screen.getByRole('gridcell', { name: /^e4,/ });

    // Last ply selected by default: ply 2 starts after e4, so the pawn is there.
    expect(pawnOnE4()).toHaveAccessibleName('e4, white p');

    // Ply 1 is played from the initial position: e4 is still empty.
    await user.click(within(list).getByText('e4'));
    expect(pawnOnE4()).toHaveAccessibleName('e4, empty');

    // Back forward again replays the later position.
    await user.click(within(list).getByText('e5'));
    expect(pawnOnE4()).toHaveAccessibleName('e4, white p');
  });

  it('shows only the reviewed player\u2019s improvements', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    const card = await screen.findByText('Where to improve');
    const section = card.closest('div.card') as HTMLElement;
    // Hero is White: only the white ply-4 mistake is listed, not black e5.
    expect(within(section).getByText('Nf6')).toBeInTheDocument();
    expect(within(section).queryByText('e5')).not.toBeInTheDocument();
  });

  it('re-analyses on demand', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const create = vi.spyOn(api, 'createGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    await user.click(await screen.findByRole('button', { name: /Re-analyse/ }));
    expect(create).toHaveBeenCalledWith(7, { force: true });
  });
});
