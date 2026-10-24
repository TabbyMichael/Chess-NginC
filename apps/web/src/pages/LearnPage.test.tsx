/**
 * Learn page (LEARN-002/003/004): skill cards render from the summary, "Practise
 * this" opens a drill board, and the verdict/reveal comes entirely from the
 * (mocked) server — a correct answer shows the solved banner and the coaching
 * line, a wrong one still reveals without claiming a solve, and "Show me" never
 * awards points. The own-games strip starts a mined puzzle.
 */
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { api } from '../lib/api-client';
import type {
  PuzzleResponse,
  TrainingAttemptResponse,
  TrainingSummaryResponse,
} from '../lib/api-types';
import LearnPage from './LearnPage';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

function summary(overrides: Partial<TrainingSummaryResponse> = {}): TrainingSummaryResponse {
  return {
    themes: {
      mate: { label: 'Checkmate', solved: 0, attempts: 0, level: 1, pct: 0 },
      hanging: { label: 'Hanging Pieces', solved: 1, attempts: 2, level: 2, pct: 0.33 },
    },
    puzzles_solved: 0,
    streak: 0,
    mine_available: 0,
    ...overrides,
  };
}

function puzzle(overrides: Partial<PuzzleResponse> = {}): PuzzleResponse {
  return {
    key: 'mate-1',
    theme: 'mate',
    name: 'Checkmate',
    level: 1,
    fen: START_FEN,
    prompt: 'It is mate in one. Find it.',
    source: 'drill',
    game_id: null,
    ply: null,
    ...overrides,
  };
}

function attempt(overrides: Partial<TrainingAttemptResponse> = {}): TrainingAttemptResponse {
  return {
    solved: true,
    solution_san: 'Qxd8#',
    solution_from: 'e2',
    solution_to: 'e4',
    why: 'The queen finishes on the open file.',
    continuation: [],
    points_awarded: 2,
    unlocked_achievements: [],
    ...overrides,
  };
}

function renderPage(summaryValue: TrainingSummaryResponse = summary()) {
  const user = userEvent.setup();
  vi.spyOn(api, 'trainingSummary').mockResolvedValue(summaryValue);
  vi.spyOn(api, 'trainingMine').mockResolvedValue([]);
  const view = render(
    <MemoryRouter>
      <LearnPage />
    </MemoryRouter>,
  );
  return { user, ...view };
}

const cell = (square: string) => screen.getByRole('gridcell', { name: new RegExp(`^${square},`) });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('LearnPage', () => {
  it('renders a card per theme from the summary', async () => {
    renderPage();
    expect(await screen.findByText('Checkmate')).toBeInTheDocument();
    expect(screen.getByText('Hanging Pieces')).toBeInTheDocument();
    // A theme with a solve already shows its ramp chip.
    expect(screen.getByText('Medium')).toBeInTheDocument();
  });

  it('opens a drill board when a theme is practised', async () => {
    const { user } = renderPage();
    await screen.findByText('Checkmate');
    const getPuzzle = vi.spyOn(api, 'trainingPuzzle').mockResolvedValue(puzzle());
    await user.click(screen.getAllByRole('button', { name: 'Practise this' })[0] as HTMLElement);

    expect(await screen.findByText('It is mate in one. Find it.')).toBeInTheDocument();
    expect(getPuzzle).toHaveBeenCalledWith('mate', undefined);
    expect(screen.getByRole('grid')).toBeInTheDocument();
  });

  it('shows the solved banner and the teaching line after a correct move', async () => {
    const { user } = renderPage();
    await screen.findByText('Checkmate');
    vi.spyOn(api, 'trainingPuzzle').mockResolvedValue(puzzle());
    await user.click(screen.getAllByRole('button', { name: 'Practise this' })[0] as HTMLElement);
    await screen.findByText('It is mate in one. Find it.');

    const submit = vi
      .spyOn(api, 'submitTrainingAttempt')
      .mockResolvedValue(attempt({ solved: true, points_awarded: 2 }));
    await user.click(cell('e2'));
    await user.click(cell('e4'));

    expect(submit).toHaveBeenCalledWith({ key: 'mate-1', uci: 'e2e4', reveal: false });
    expect(await screen.findByText('Solved! +2 points')).toBeInTheDocument();
    expect(screen.getByText('The queen finishes on the open file.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next puzzle' })).toBeInTheDocument();
  });

  it('reveals without claiming a solve after a wrong move', async () => {
    const { user } = renderPage();
    await screen.findByText('Checkmate');
    vi.spyOn(api, 'trainingPuzzle').mockResolvedValue(puzzle());
    await user.click(screen.getAllByRole('button', { name: 'Practise this' })[0] as HTMLElement);
    await screen.findByText('It is mate in one. Find it.');

    vi.spyOn(api, 'submitTrainingAttempt').mockResolvedValue(
      attempt({ solved: false, points_awarded: 0 }),
    );
    await user.click(cell('e2'));
    await user.click(cell('e4'));

    expect(await screen.findByText(/Not this drill/)).toBeInTheDocument();
    // The answer is still shown, but nothing claims a solve.
    expect(screen.getByText('Qxd8#')).toBeInTheDocument();
    expect(screen.queryByText(/Solved!/)).not.toBeInTheDocument();
  });

  it('never awards points on a "Show me" reveal', async () => {
    const { user } = renderPage();
    await screen.findByText('Checkmate');
    vi.spyOn(api, 'trainingPuzzle').mockResolvedValue(puzzle());
    await user.click(screen.getAllByRole('button', { name: 'Practise this' })[0] as HTMLElement);
    await screen.findByText('It is mate in one. Find it.');

    const submit = vi
      .spyOn(api, 'submitTrainingAttempt')
      .mockResolvedValue(attempt({ solved: false, points_awarded: 0 }));
    await user.click(screen.getByRole('button', { name: /Show me/ }));

    expect(submit).toHaveBeenCalledWith({ key: 'mate-1', uci: '', reveal: true });
    expect(await screen.findByText(/Not this drill/)).toBeInTheDocument();
  });

  it('starts a mined puzzle from the own-games strip', async () => {
    const { user } = renderPage(summary({ mine_available: 3 }));
    await screen.findByText('Checkmate');
    const getPuzzle = vi
      .spyOn(api, 'trainingPuzzle')
      .mockResolvedValue(puzzle({ key: 'mine:7:5', source: 'game', theme: 'missed' }));
    await user.click(screen.getByRole('button', { name: 'Drill a missed move' }));

    expect(getPuzzle).toHaveBeenCalledWith(undefined, 'game');
    expect(await screen.findByText('It is mate in one. Find it.')).toBeInTheDocument();
  });
});
