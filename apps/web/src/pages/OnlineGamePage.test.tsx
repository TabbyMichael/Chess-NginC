/**
 * Online game page tests: seat detection, moves over the fake socket,
 * authoritative game_state broadcasts re-rendering the board, the REST
 * fallback when the socket is down, and turn gating on the client side.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AchievementProvider } from '../app/AchievementContext';
import { AuthProvider } from '../app/AuthContext';
import { api } from '../lib/api-client';
import type { AchievementResponse, GameResponse } from '../lib/api-types';
import OnlineGamePage from './OnlineGamePage';

// Fake socket transport: captures lifecycle callbacks, records sends, and
// lets tests push server events through the page's onEvent callback.
const ws = vi.hoisted(() => ({
  sent: [] as Record<string, unknown>[],
  emit: null as ((event: { type: string; payload?: unknown }) => void) | null,
  setStatus: null as ((connected: boolean) => void) | null,
  acceptSends: true,
}));

vi.mock('../lib/online-ws', () => ({
  OnlineSocket: class {
    constructor(
      _gameId: number,
      onEvent: (event: { type: string; payload?: unknown }) => void,
      onStatus: (connected: boolean) => void,
    ) {
      ws.emit = onEvent;
      ws.setStatus = onStatus;
    }
    connect(): void {
      ws.setStatus?.(true);
    }
    send(action: Record<string, unknown>): boolean {
      if (!ws.acceptSends) return false;
      ws.sent.push(action);
      return true;
    }
    close(): void {}
  },
}));

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';

function game(overrides: Partial<GameResponse> = {}): GameResponse {
  return {
    id: 7,
    mode: 'online',
    status: 'active',
    fen: START_FEN,
    version: 1,
    moves: [],
    white_user_id: 1,
    black_user_id: 2,
    ...overrides,
  };
}

function renderOnline(path = '/online/7', me = { id: 1, email: 'a@b.co', points: 0 }) {
  const user = userEvent.setup();
  vi.spyOn(api, 'me').mockResolvedValue(me);
  vi.spyOn(api, 'getOnlineGame').mockResolvedValue(game());
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/online/:id" element={<OnlineGamePage />} />
          <Route path="/lobby" element={<p>Lobby</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

async function clickMove(user: ReturnType<typeof userEvent.setup>, from: string, to: string) {
  await user.click(await screen.findByRole('gridcell', { name: new RegExp(`^${from},`) }));
  await user.click(screen.getByRole('gridcell', { name: new RegExp(`^${to},`) }));
}

describe('OnlineGamePage (online-plan §6)', () => {
  it('shows the seat and connects the socket', async () => {
    renderOnline();
    expect(await screen.findByText(/You play White/)).toBeInTheDocument();
    expect(await screen.findByText('Live')).toBeInTheDocument();
  });

  it('detects the Black seat', async () => {
    renderOnline('/online/7', { id: 2, email: 'b@b.co', points: 0 });
    expect(await screen.findByText(/You play Black/)).toBeInTheDocument();
  });

  it('sends moves over the socket and applies the broadcast', async () => {
    const { user } = renderOnline();
    await screen.findByText(/You play White/);
    ws.sent.length = 0;

    await clickMove(user, 'e2', 'e4');
    await waitFor(() =>
      expect(ws.sent).toContainEqual({
        type: 'move',
        payload: { uci: 'e2e4', expected_version: 1 },
      }),
    );

    // Server answers with the authoritative state; board follows it.
    ws.emit?.({
      type: 'game_state',
      payload: game({
        fen: AFTER_E4,
        version: 2,
        moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }],
      }),
    });
    expect(await screen.findByRole('gridcell', { name: /^e4,/ })).toHaveAccessibleName(
      'e4, white p',
    );
    expect(screen.getByRole('list', { name: 'move history' })).toHaveTextContent('e4');
  });

  it('falls back to REST when the socket cannot send', async () => {
    const { user } = renderOnline();
    await screen.findByText(/You play White/);
    ws.acceptSends = false;
    const submit = vi.spyOn(api, 'submitOnlineMove').mockResolvedValue(
      game({
        fen: AFTER_E4,
        version: 2,
        moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }],
      }),
    );

    await clickMove(user, 'e2', 'e4');
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(7, { uci: 'e2e4', expected_version: 1 }),
    );
    expect(await screen.findByText('e4')).toBeInTheDocument();
    ws.acceptSends = true;
  });

  it('blocks the board when it is not your turn', async () => {
    const submit = vi.spyOn(api, 'submitOnlineMove');
    const { user } = renderOnline();
    await screen.findByText(/You play White/);
    ws.emit?.({ type: 'game_state', payload: game({ fen: AFTER_E4, version: 2 }) });
    ws.sent.length = 0;

    await clickMove(user, 'e7', 'e5');
    expect(ws.sent).toHaveLength(0);
    expect(submit).not.toHaveBeenCalled();
  });

  it('resigns through the confirm dialog', async () => {
    const { user } = renderOnline();
    await screen.findByText(/You play White/);
    ws.sent.length = 0;

    await user.click(screen.getByRole('button', { name: 'Resign' }));
    await user.click(screen.getByRole('button', { name: 'Resign game' }));
    await waitFor(() => expect(ws.sent).toContainEqual({ type: 'resign' }));
  });

  it('handles socket errors with a sound, no banner', async () => {
    renderOnline();
    await screen.findByText(/You play White/);
    ws.emit?.({ type: 'error', payload: { detail: 'It is not your turn' } });
    // A rejected move is felt, not read: the error is an audio cue only.
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });

  it('celebrates the private achievement event', async () => {
    const unlock: AchievementResponse = {
      key: 'moves_total-10',
      title: 'Opening Moves',
      description: 'Play 10 moves',
      metric: 'moves_total',
      threshold: 10,
      tier: 'bronze',
      group: 'play',
    };
    vi.spyOn(api, 'newAchievements').mockResolvedValue([]);
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'getOnlineGame').mockResolvedValue(game());
    render(
      <MemoryRouter initialEntries={['/online/7']}>
        <AuthProvider>
          <AchievementProvider>
            <Routes>
              <Route path="/online/:id" element={<OnlineGamePage />} />
            </Routes>
          </AchievementProvider>
        </AuthProvider>
      </MemoryRouter>,
    );

    await screen.findByText(/You play White/);
    ws.emit?.({ type: 'achievement', payload: { items: [unlock] } });
    // The queue only renders once the auth restore resolves (a `user` gates it),
    // so this waits on two async chains at once — allow the page some slack.
    expect(
      await screen.findByText('Opening Moves', undefined, { timeout: 3000 }),
    ).toBeInTheDocument();
  });

  it('plays without a celebration provider mounted', async () => {
    // The queue is presentation on top of the board: a bare page still works.
    renderOnline();
    expect(await screen.findByText(/You play White/)).toBeInTheDocument();
    ws.emit?.({
      type: 'achievement',
      payload: {
        items: [
          {
            key: 'moves_total-10',
            title: 'Opening Moves',
            description: 'Play 10 moves',
            metric: 'moves_total',
            threshold: 10,
            tier: 'bronze',
            group: 'play',
          },
        ],
      },
    });
    expect(screen.queryByText('Opening Moves')).not.toBeInTheDocument();
  });
});
