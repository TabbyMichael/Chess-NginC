/**
 * Celebration queue tests (ACH-006/007): unlocks arrive from the lazy catch-up
 * read and from response rides, are celebrated exactly once, and are
 * acknowledged back to the server when the toast goes away.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AchievementProvider } from './AchievementContext';
import { AuthProvider } from './AuthContext';
import { useAchievementRide, type UnlocksCarrier } from './useAchievementRide';
import { api } from '../lib/api-client';
import type { AchievementResponse } from '../lib/api-types';

function item(key: string): AchievementResponse {
  return {
    key,
    title: `Title ${key}`,
    description: `Description ${key}`,
    metric: 'moves_total',
    threshold: 10,
    tier: 'bronze',
    group: 'play',
  };
}

function RideConsumer({ game }: { game: UnlocksCarrier | null }) {
  useAchievementRide(game);
  return <p>consumer</p>;
}

function renderProvider(ui?: ReactNode) {
  const user = userEvent.setup();
  const view = render(
    <AuthProvider>
      <AchievementProvider>{ui ?? <p>child</p>}</AchievementProvider>
    </AuthProvider>,
  );
  return { user, ...view };
}

function toasts() {
  return document.querySelectorAll('.celebration');
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AchievementProvider', () => {
  it('catches up on unlocks the server has not celebrated yet', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    const news = vi.spyOn(api, 'newAchievements').mockResolvedValue([item('a')]);
    renderProvider();

    expect(await screen.findByText('Title a')).toBeInTheDocument();
    expect(news).toHaveBeenCalledTimes(1);
  });

  it('stays quiet for an anonymous visitor', async () => {
    vi.spyOn(api, 'me').mockRejectedValue(new Error('no session'));
    const news = vi.spyOn(api, 'newAchievements');
    renderProvider();

    await waitFor(() => expect(screen.getByText('child')).toBeInTheDocument());
    expect(news).not.toHaveBeenCalled();
  });

  it('celebrates an unlock that rides on a game response', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'newAchievements').mockResolvedValue([]);
    const game: UnlocksCarrier = { unlocked_achievements: [item('ride')] };
    renderProvider(<RideConsumer game={game} />);

    expect(await screen.findByText('Title ride')).toBeInTheDocument();
  });

  it('never celebrates the same achievement twice', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'newAchievements').mockResolvedValue([item('a')]);
    const game: UnlocksCarrier = { unlocked_achievements: [item('a')] };
    renderProvider(<RideConsumer game={game} />);

    await screen.findByText('Title a');
    await waitFor(() => expect(toasts()).toHaveLength(1));
    expect(screen.getAllByText('Title a')).toHaveLength(1);
  });

  it('acknowledges a dismissal so the moment is not replayed', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'newAchievements').mockResolvedValue([item('a')]);
    const seen = vi
      .spyOn(api, 'markAchievementsSeen')
      .mockResolvedValue({ message: 'Acknowledged 1 achievement(s)' });
    const { user } = renderProvider();

    await screen.findByText('Title a');
    await user.click(screen.getByRole('button', { name: 'Dismiss Title a' }));

    await waitFor(() => expect(toasts()).toHaveLength(0));
    expect(seen).toHaveBeenCalledWith(['a']);
  });

  it('queues distinct unlocks one after the other', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'newAchievements').mockResolvedValue([item('a'), item('b')]);
    const { user } = renderProvider();

    // One toast at a time: closing the first reveals the second.
    expect(await screen.findByText('Title a')).toBeInTheDocument();
    expect(screen.queryByText('Title b')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Dismiss Title a' }));
    expect(await screen.findByText('Title b')).toBeInTheDocument();
  });

  it('ignores a failed catch-up read — celebrations are decorative', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'newAchievements').mockRejectedValue(new Error('offline'));
    renderProvider();

    expect(await screen.findByText('child')).toBeInTheDocument();
    expect(toasts()).toHaveLength(0);
  });
});
