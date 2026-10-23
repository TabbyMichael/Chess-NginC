import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../app/AuthContext';
import { ApiError, api } from '../lib/api-client';
import type { GameResponse } from '../lib/api-types';
import GamePage from './GamePage';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';

function game(overrides: Partial<GameResponse> = {}): GameResponse {
  return {
    id: 7,
    mode: 'local',
    status: 'active',
    fen: START_FEN,
    version: 1,
    moves: [],
    ...overrides,
  };
}

function renderGame(path = '/games/7') {
  const user = userEvent.setup();
  vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
  // Each test spies `getGame` before calling this so load states are explicit.
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/games/:id" element={<GamePage />} />
          <Route path="/online/:id" element={<p>Online board</p>} />
          <Route path="/" element={<p>Dashboard</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

/**
 * Click a source square then a destination square. Squares are `gridcell`
 * buttons inside a `grid`, so the explicit role is required.
 */
async function clickMove(user: ReturnType<typeof userEvent.setup>, from: string, to: string) {
  await user.click(await screen.findByRole('gridcell', { name: new RegExp(`^${from},`) }));
  await user.click(screen.getByRole('gridcell', { name: new RegExp(`^${to},`) }));
}

describe('GamePage load (WEB-024/025)', () => {
  it('rejects a non-numeric game id without fetching', async () => {
    const getGame = vi.spyOn(api, 'getGame');
    renderGame('/games/not-a-number');

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid game id.');
    expect(getGame).not.toHaveBeenCalled();
  });

  it('resumes an existing game from the API', async () => {
    const resumed = game({
      fen: AFTER_E4,
      version: 2,
      moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }],
    });
    const getGame = vi.spyOn(api, 'getGame').mockResolvedValue(resumed);
    renderGame('/games/7');

    expect(await screen.findByRole('heading', { name: /Game #7/ })).toBeInTheDocument();
    expect(getGame).toHaveBeenCalledWith(7);
    expect(screen.getByRole('list', { name: 'move history' })).toHaveTextContent('e4');
    // Board reflects the resumed position: e4 occupied, e2 empty.
    expect(screen.getByRole('gridcell', { name: /^e4,/ })).toHaveAccessibleName('e4, white p');
    expect(screen.getByRole('gridcell', { name: /^e2,/ })).toHaveAccessibleName('e2, empty');
  });

  it('redirects online games to the /online/:id board', async () => {
    // Legacy routes refuse online games, so the page must hand the row over.
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ mode: 'online', white_user_id: 1, black_user_id: 2 }),
    );
    renderGame('/games/7');

    expect(await screen.findByText('Online board')).toBeInTheDocument();
  });

  it('shows an error state when the game cannot be loaded', async () => {
    vi.spyOn(api, 'getGame').mockRejectedValueOnce(new ApiError(404, 'Game not found'));
    renderGame('/games/7');

    expect(await screen.findByRole('alert')).toHaveTextContent('Game not found');
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
  });
});

describe('GamePage moves (WEB-011/019/025)', () => {
  it('submits a click-to-move with the expected version', async () => {
    const submit = vi
      .spyOn(api, 'submitMove')
      .mockResolvedValue(
        game({ fen: AFTER_E4, version: 2, moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }] }),
      );
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');

    expect(submit).toHaveBeenCalledWith(7, { uci: 'e2e4', expected_version: 1 });
    expect(await screen.findByRole('list', { name: 'move history' })).toHaveTextContent('e4');
  });

  it('surfaces an illegal move as an error without changing the board', async () => {
    vi.spyOn(api, 'submitMove').mockRejectedValueOnce(new ApiError(422, 'Illegal move'));
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e5');

    expect(await screen.findByRole('alert')).toHaveTextContent('Illegal move');
    // Board unchanged: pawn still on e2.
    expect(screen.getByRole('gridcell', { name: /^e2,/ })).toHaveAccessibleName('e2, white p');
  });

  it('re-syncs the board after a 409 version conflict', async () => {
    vi.spyOn(api, 'submitMove').mockRejectedValueOnce(new ApiError(409, 'Game changed'));
    // First call is the mount, second is the conflict refetch (WEB-025).
    const getGame = vi
      .spyOn(api, 'getGame')
      .mockResolvedValueOnce(game())
      .mockResolvedValueOnce(game({ fen: AFTER_E4, version: 5 }));
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');

    expect(await screen.findByRole('alert')).toHaveTextContent('Game changed');
    await waitFor(() => expect(getGame).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByRole('gridcell', { name: /^e4,/ })).toHaveAccessibleName('e4, white p'),
    );
  });

  it('undoes a move', async () => {
    const undo = vi.spyOn(api, 'undoMove').mockResolvedValue(game({ version: 3 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ version: 4, moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }] }),
    );
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: 'Undo' }));

    expect(undo).toHaveBeenCalledWith(7, { expected_version: 4 });
  });

  it('resigns the game after confirmation and locks the controls', async () => {
    vi.spyOn(api, 'resignGame').mockResolvedValue(game({ status: 'resigned', version: 2 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: 'Resign' }));
    // Destructive actions ask for confirmation first.
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Resign game' }));

    expect(await screen.findByText(/Resigned/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resign' })).toBeDisabled();
  });

  it('does not resign when the confirmation is cancelled', async () => {
    const resign = vi.spyOn(api, 'resignGame');
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: 'Resign' }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(resign).not.toHaveBeenCalled();
  });

  it('resets to the start by undoing every move', async () => {
    const undo = vi
      .spyOn(api, 'undoMove')
      // Each undo removes one move from the server's view.
      .mockResolvedValueOnce(
        game({
          version: 3,
          moves: [
            { uci: 'e2e4', san: 'e4', move_number: 1 },
            { uci: 'e7e5', san: 'e5', move_number: 1 },
          ],
        }),
      )
      .mockResolvedValueOnce(
        game({ version: 2, moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }] }),
      )
      .mockResolvedValue(game({ version: 1, moves: [] }));
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        version: 4,
        moves: [
          { uci: 'e2e4', san: 'e4', move_number: 1 },
          { uci: 'e7e5', san: 'e5', move_number: 1 },
          { uci: 'g1f3', san: 'Nf3', move_number: 2 },
        ],
      }),
    );
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: /Reset to start/ }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Reset game' }));

    expect(undo).toHaveBeenCalledTimes(3);
    await waitFor(() => expect(undo).toHaveBeenLastCalledWith(7, { expected_version: 2 }));
    // Empty move list renders the empty state, not the <ol>.
    expect(await screen.findByText('No moves yet. White to move.')).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'move history' })).not.toBeInTheDocument();
  });
});

describe('GamePage promotion (WEB-015)', () => {
  it('asks which piece to promote to before sending the move', async () => {
    const submit = vi.spyOn(api, 'submitMove').mockResolvedValue(game({ version: 2 }));
    // White pawn on b7 ready to promote on a8.
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ fen: '1nb1kbn1/1P1ppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' }),
    );
    const { user } = renderGame('/games/7');

    await clickMove(user, 'b7', 'a8');

    // Picker appears before any request is sent.
    const dialog = await screen.findByRole('dialog');
    expect(submit).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole('button', { name: /promote to n/i }));

    expect(submit).toHaveBeenCalledWith(7, { uci: 'b7a8n', expected_version: 1 });
  });
});

describe('GamePage status and engine (WEB-013/014/020/021)', () => {
  it('announces checkmate as game over and locks controls', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        status: 'checkmate',
        fen: 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3',
      }),
    );
    renderGame('/games/7');

    expect(await screen.findByText(/Checkmate/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resign' })).toBeDisabled();
  });

  it('announces stalemate as a draw', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ status: 'stalemate', fen: 'k7/8/1Q6/8/8/8/8/K7 b - - 0 1' }),
    );
    renderGame('/games/7');

    expect(await screen.findByText(/Stalemate/)).toBeInTheDocument();
  });

  it('offers an engine move in computer mode', async () => {
    const engineMove = vi.spyOn(api, 'engineMove').mockResolvedValue(game({ version: 2 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer' }));
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: /Engine move/ }));

    expect(engineMove).toHaveBeenCalledWith(7, {
      expected_version: 1,
      max_depth: 3,
      max_time_ms: 2000,
    });
  });

  it('hides the engine move button in local mode', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'local' }));
    renderGame('/games/7');

    await screen.findByRole('heading', { name: /Game #7/ });
    expect(screen.queryByRole('button', { name: /Engine move/ })).not.toBeInTheDocument();
  });
});

describe('GamePage status, promotion and engine (WEB-013/015/020/021)', () => {
  it('asks which piece to promote to, then sends the chosen letter', async () => {
    const submit = vi.spyOn(api, 'submitMove').mockResolvedValue(game({ version: 2 }));
    // White pawn on b7 ready to promote on a8.
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ fen: '1nb1kbn1/1P1ppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' }),
    );
    const { user } = renderGame('/games/7');

    await clickMove(user, 'b7', 'a8');

    // The dialog appears before any request is sent.
    const dialog = await screen.findByRole('dialog');
    expect(submit).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole('button', { name: /promote to n/i }));

    expect(submit).toHaveBeenCalledWith(7, { uci: 'b7a8n', expected_version: 1 });
  });

  it('announces checkmate as game over and locks controls', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        status: 'checkmate',
        fen: 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3',
      }),
    );
    renderGame('/games/7');

    expect(await screen.findByText(/Checkmate/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resign' })).toBeDisabled();
  });

  it('announces stalemate as a draw', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ status: 'stalemate', fen: 'k7/8/1Q6/8/8/8/8/K7 b - - 0 1' }),
    );
    renderGame('/games/7');
    expect(await screen.findByText(/Stalemate/)).toBeInTheDocument();
  });

  it('offers an engine move in computer mode', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer' }));
    renderGame('/games/7');
    expect(await screen.findByRole('button', { name: /Engine move/ })).toBeInTheDocument();
  });

  it('hides the engine move button in local mode', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'local' }));
    renderGame('/games/7');
    await screen.findByRole('heading', { name: /Game #7/ });
    expect(screen.queryByRole('button', { name: /Engine move/ })).not.toBeInTheDocument();
  });

  it('requests an engine move at the chosen depth', async () => {
    const engineMove = vi.spyOn(api, 'engineMove').mockResolvedValue(game({ version: 2 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer' }));
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: /Engine move/ }));

    expect(engineMove).toHaveBeenCalledWith(7, {
      expected_version: 1,
      max_depth: 3,
      max_time_ms: 2000,
    });
  });
});

describe('GamePage legal-move hints', () => {
  it('lights empty target squares with dots and capture targets with rings', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('gridcell', { name: /^e2,/ }));

    // Pawn pushes show subtle dots; the e7 pawn is not a legal target here.
    expect(screen.getByRole('gridcell', { name: /^e3,/ })).toHaveClass('hint-target');
    expect(screen.getByRole('gridcell', { name: /^e4,/ })).toHaveClass('hint-target');
    expect(screen.getByRole('gridcell', { name: /^e7,/ })).not.toHaveClass('hint-capture');

    // Deselect, then jump the knight: f3 is a legal target (subtle dot).
    await user.click(screen.getByRole('gridcell', { name: /^e2,/ }));
    await user.click(await screen.findByRole('gridcell', { name: /^g1,/ }));
    expect(screen.getByRole('gridcell', { name: /^f3,/ })).toHaveClass('hint-target');
  });

  it('shows capture rings on enemy pieces', async () => {
    // After 1.e4 d5 the e4 pawn can capture d5.
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        fen: 'rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2',
        version: 3,
        moves: [
          { uci: 'e2e4', san: 'e4', move_number: 1 },
          { uci: 'd7d5', san: 'd5', move_number: 1 },
        ],
      }),
    );
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('gridcell', { name: /^e4,/ }));

    expect(screen.getByRole('gridcell', { name: /^d5,/ })).toHaveClass('hint-capture');
  });
});

describe('GamePage auto-engine reply', () => {
  it('answers the played move in computer mode without a button click', async () => {
    const engineMove = vi
      .spyOn(api, 'engineMove')
      // Engine answers 1.e4 with 1...e5: FEN tail flips back to white to move.
      .mockResolvedValue(
        game({
          mode: 'computer',
          fen: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2',
          version: 3,
          moves: [
            { uci: 'e2e4', san: 'e4', move_number: 1 },
            { uci: 'e7e5', san: 'e5', move_number: 1 },
          ],
        }),
      );
    vi.spyOn(api, 'submitMove').mockResolvedValueOnce(
      game({
        mode: 'computer',
        fen: AFTER_E4,
        version: 2,
        moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }],
      }),
    );
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer' }));
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');

    // The engine reply fires on its own once it is Black's turn.
    await waitFor(() =>
      expect(engineMove).toHaveBeenCalledWith(7, {
        expected_version: 2,
        max_depth: 3,
        max_time_ms: 2000,
      }),
    );
    // And the reply landed: board is White to move again.
    expect(await screen.findByRole('gridcell', { name: /^e5,/ })).toBeInTheDocument();
  });

  it('does not auto-request when the player is already to move', async () => {
    const engineMove = vi.spyOn(api, 'engineMove');
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer' }));
    renderGame('/games/7');

    await screen.findByRole('heading', { name: /Game #7/ });
    // White to move at load: no automatic engine call, only the manual button.
    expect(engineMove).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Engine move/ })).toBeInTheDocument();
  });

  it('never auto-plays in local mode', async () => {
    const engineMove = vi.spyOn(api, 'engineMove');
    vi.spyOn(api, 'submitMove').mockResolvedValue(game({ fen: AFTER_E4, version: 2 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'local' }));
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');
    await waitFor(() => expect(engineMove).not.toHaveBeenCalled());
  });
});
