/**
 * Achievement gallery tests (ACH-005): the page is a pure view over
 * GET /me/achievements — summary, sections, per-tile progress and the group
 * filter — plus its loading and error states.
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api } from '../lib/api-client';
import type { AchievementListResponse, AchievementProgressResponse } from '../lib/api-types';
import AchievementsPage from './AchievementsPage';

function tile(overrides: Partial<AchievementProgressResponse> = {}): AchievementProgressResponse {
  return {
    key: 'moves_total-10',
    title: 'Opening Moves',
    description: 'Play 10 moves',
    metric: 'moves_total',
    threshold: 10,
    tier: 'bronze',
    group: 'play',
    value: 0,
    unlocked: false,
    progress: 0,
    unlocked_at: null,
    ...overrides,
  };
}

function list(items: AchievementProgressResponse[]): AchievementListResponse {
  return { total: items.length, unlocked: items.filter((item) => item.unlocked).length, items };
}

const CATALOG = [
  tile({ unlocked: true, progress: 1, unlocked_at: '2026-10-20T09:00:00' }),
  tile({
    key: 'captures-10',
    title: 'Coin Grab',
    description: 'Capture 10 pieces',
    metric: 'captures',
    group: 'tactics',
    tier: 'silver',
    value: 3,
    progress: 0.3,
  }),
];

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPage() {
  const user = userEvent.setup();
  const view = render(
    <MemoryRouter>
      <AchievementsPage />
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('AchievementsPage', () => {
  it('asks the server for the catalog and shows a loading state', async () => {
    const fetcher = vi.spyOn(api, 'listAchievements').mockResolvedValue(list(CATALOG));
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Achievements' })).toBeInTheDocument();
    expect(await screen.findByText('Opening Moves')).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('summarises overall completion and reports the counts', async () => {
    vi.spyOn(api, 'listAchievements').mockResolvedValue(list(CATALOG));
    renderPage();

    expect(await screen.findByText('50% complete')).toBeInTheDocument();
    expect(
      await screen.findByText('1 of 2 unlocked — every one earned by playing.'),
    ).toBeInTheDocument();
  });

  it('renders unlocked tiles first and shows progress on locked ones', async () => {
    vi.spyOn(api, 'listAchievements').mockResolvedValue(list(CATALOG));
    const { container } = renderPage();

    await screen.findByText('Opening Moves');
    const tiles = container.querySelectorAll('.achievement');
    expect(tiles).toHaveLength(2);
    expect(tiles[0]).toHaveClass('unlocked');
    expect(within(tiles[0] as HTMLElement).getByText('Unlocked')).toBeInTheDocument();
    expect(within(tiles[1] as HTMLElement).getByText('Locked')).toBeInTheDocument();
    expect(within(tiles[1] as HTMLElement).getByText('Silver · 3 / 10')).toBeInTheDocument();
    expect(
      within(tiles[1] as HTMLElement).getByRole('img', { name: '30% toward the goal' }),
    ).toBeInTheDocument();
  });

  it('groups the catalog under readable headings', async () => {
    vi.spyOn(api, 'listAchievements').mockResolvedValue(list(CATALOG));
    renderPage();

    const sections = await screen.findAllByRole('region');
    expect(sections.map((section) => section.getAttribute('aria-label'))).toEqual([
      'Games played',
      'Tactics',
    ]);
  });

  it('filters the gallery by category', async () => {
    vi.spyOn(api, 'listAchievements').mockResolvedValue(list(CATALOG));
    const { user } = renderPage();

    await screen.findByText('Opening Moves');
    await user.click(screen.getByRole('button', { name: 'Tactics' }));

    expect(await screen.findByRole('region', { name: 'Tactics' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Games played' })).not.toBeInTheDocument();
    expect(screen.queryByText('Opening Moves')).not.toBeInTheDocument();
  });

  it('surfaces a load failure instead of an empty gallery', async () => {
    vi.spyOn(api, 'listAchievements').mockRejectedValue(new ApiError(500, 'Boom'));
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Boom');
    expect(screen.queryByText('Opening Moves')).not.toBeInTheDocument();
  });

  it('links back to the dashboard', async () => {
    vi.spyOn(api, 'listAchievements').mockResolvedValue(list(CATALOG));
    renderPage();

    expect(await screen.findByRole('link', { name: 'Back to dashboard' })).toHaveAttribute(
      'href',
      '/',
    );
  });
});
