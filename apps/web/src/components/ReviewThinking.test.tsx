/**
 * The review "thinking" loader: it replays a game *backwards* while analysis
 * runs, on a fake clock. These tests pin the load-bearing behaviour — start on
 * the newest position, step one ply back per tick, loop at the opening, fall
 * back to a static board when there is nothing to replay, and stop the timer on
 * unmount (no leaked interval).
 */
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ReviewThinking from './ReviewThinking';
import { api } from '../lib/api-client';
import type { GameResponse } from '../lib/api-types';

const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';
// After 1. e4 e5 — Black's pawn on e5, White's on e4.
const TWO_PLIES = [
  { uci: 'e2e4', san: 'e4', move_number: 1 },
  { uci: 'e7e5', san: 'e5', move_number: 1 },
];

function detail(moves: GameResponse['moves']): GameResponse {
  return { id: 7, mode: 'computer', status: 'active', fen: AFTER_E4, version: 3, moves };
}

/** Render, mocking the game fetch, and flush the resolving promise under fake timers. */
async function renderFetched(moves: GameResponse['moves']) {
  vi.spyOn(api, 'getGame').mockResolvedValue(detail(moves));
  const view = render(<ReviewThinking gameId={7} />);
  await act(async () => {
    /* let the getGame promise resolve */
  });
  return view;
}

const cell = (square: string) => screen.getByRole('gridcell', { name: new RegExp(`^${square},`) });

describe('ReviewThinking', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.clearAllTimers();
    cleanup();
    vi.useRealTimers();
  });

  it('opens on the newest position', async () => {
    await renderFetched(TWO_PLIES);
    // Last replayed ply is after 1...e5, so both centre pawns are home.
    expect(cell('e5')).toHaveAccessibleName('e5, black p');
    expect(cell('e4')).toHaveAccessibleName('e4, white p');
  });

  it('steps one ply backwards each interval', async () => {
    await renderFetched(TWO_PLIES);
    await act(async () => {
      vi.advanceTimersByTime(450);
    });
    // Now on the earlier position (after 1. e4): e5 is empty again.
    expect(cell('e5')).toHaveAccessibleName('e5, empty');
    expect(cell('e4')).toHaveAccessibleName('e4, white p');
  });

  it('loops back to the newest position at the start', async () => {
    await renderFetched(TWO_PLIES);
    await act(async () => {
      vi.advanceTimersByTime(450); // -> first ply
    });
    await act(async () => {
      vi.advanceTimersByTime(450); // -> wraps to the last ply
    });
    expect(cell('e5')).toHaveAccessibleName('e5, black p');
  });

  it('falls back to a static start board when the fetch rejects', async () => {
    vi.spyOn(api, 'getGame').mockRejectedValue(new Error('network'));
    render(<ReviewThinking gameId={7} />);
    await act(async () => {
      /* let the rejection settle */
    });
    expect(cell('e2')).toHaveAccessibleName('e2, white p');
    expect(cell('e4')).toHaveAccessibleName('e4, empty');
    expect(screen.getByText(/Stockfish is replaying/)).toBeInTheDocument();
  });

  it('falls back to a static board when the game has no moves', async () => {
    await renderFetched([]);
    expect(cell('e2')).toHaveAccessibleName('e2, white p');
  });

  it('uses supplied positions without fetching the game', async () => {
    const getGame = vi.spyOn(api, 'getGame');
    render(<ReviewThinking gameId={7} fens={[AFTER_E4]} />);
    expect(cell('e4')).toHaveAccessibleName('e4, white p');
    expect(getGame).not.toHaveBeenCalled();
  });

  it('clears its interval on unmount', async () => {
    const { unmount } = await renderFetched(TWO_PLIES);
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
