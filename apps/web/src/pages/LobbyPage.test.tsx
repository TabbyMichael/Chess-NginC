/**
 * Lobby page tests: queue → matched navigates into the game; queued shows
 * the waiting state with a working cancel; game list renders online rows.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../lib/api-client';
import type { GameResponse } from '../lib/api-types';
import LobbyPage from './LobbyPage';

function game(overrides: Partial<GameResponse> = {}): GameResponse {
  return {
    id: 9,
    mode: 'online',
    status: 'active',
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    version: 1,
    moves: [],
    white_user_id: 1,
    black_user_id: 2,
    ...overrides,
  };
}

function renderLobby(onlineGames: GameResponse[] = []) {
  const user = userEvent.setup();
  vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
  vi.spyOn(api, 'queueStatus').mockResolvedValue({ status: 'idle' });
  vi.spyOn(api, 'listOnlineGames').mockResolvedValue(onlineGames);
  const view = render(
    <MemoryRouter initialEntries={['/lobby']}>
      <Routes>
        <Route path="/lobby" element={<LobbyPage />} />
        <Route path="/online/:id" element={<p>Online game page</p>} />
      </Routes>
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('LobbyPage (online-plan §5)', () => {
  it('jumps to the game immediately when the queue matches', async () => {
    const { user } = renderLobby();
    vi.spyOn(api, 'joinQueue').mockResolvedValue({ status: 'matched', game_id: 42, color: 'w' });

    await user.click(screen.getByRole('button', { name: /Join the queue/ }));

    expect(await screen.findByText('Online game page')).toBeInTheDocument();
  });

  it('shows the waiting state and cancels the queue', async () => {
    const { user } = renderLobby();
    vi.spyOn(api, 'joinQueue').mockResolvedValue({ status: 'queued' });
    const leave = vi.spyOn(api, 'leaveQueue').mockResolvedValue(undefined);

    await user.click(screen.getByRole('button', { name: /Join the queue/ }));
    expect(await screen.findByRole('status')).toHaveTextContent('Waiting for an opponent');

    await user.click(screen.getByRole('button', { name: /Leave queue/ }));
    expect(leave).toHaveBeenCalled();
    expect(await screen.findByRole('button', { name: /Join the queue/ })).toBeEnabled();
  });

  it('lists previous online games with links into the board', async () => {
    renderLobby([game(), game({ id: 10, status: 'resigned' })]);

    const link = await screen.findByRole('link', { name: /Game #9/ });
    expect(link).toHaveAttribute('href', '/online/9');
  });

  it('surfaces queue errors as an alert', async () => {
    const { user } = renderLobby();
    vi.spyOn(api, 'joinQueue').mockRejectedValue(new Error('server shrugged'));

    await user.click(screen.getByRole('button', { name: /Join the queue/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to join the queue');
  });
});
