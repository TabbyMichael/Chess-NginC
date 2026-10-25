/**
 * Achievement presentation helpers (ACH-005): ordering, labelling, progress
 * maths and the celebration de-duplication rules the gallery and the toast
 * queue both depend on.
 */
import { describe, expect, it } from 'vitest';

import {
  filterByGroup,
  formatCounter,
  formatUnlockedAt,
  groupLabel,
  groupsOf,
  mergeQueue,
  newestUnlocked,
  progressPercent,
  sortForGallery,
} from './achievements';
import type { AchievementProgressResponse, AchievementResponse } from './api-types';

function entry(overrides: Partial<AchievementResponse> = {}): AchievementResponse {
  return {
    key: 'moves_total-10',
    title: 'Opening Moves',
    description: 'Play 10 moves',
    metric: 'moves_total',
    threshold: 10,
    tier: 'bronze',
    group: 'play',
    ...overrides,
  };
}

function progress(
  overrides: Partial<AchievementProgressResponse> = {},
): AchievementProgressResponse {
  return { ...entry(), value: 0, unlocked: false, progress: 0, unlocked_at: null, ...overrides };
}

describe('groupLabel / groupsOf', () => {
  it('names the known groups and falls back to the raw key', () => {
    expect(groupLabel('play')).toBe('Games played');
    expect(groupLabel('mystery')).toBe('mystery');
  });

  it('lists groups in catalog order without repeats', () => {
    const items = [
      entry({ key: 'a', group: 'play' }),
      entry({ key: 'b', group: 'tactics' }),
      entry({ key: 'c', group: 'play' }),
    ];
    expect(groupsOf(items)).toEqual(['play', 'tactics']);
  });
});

describe('filterByGroup', () => {
  const items = [progress({ key: 'a', group: 'play' }), progress({ key: 'b', group: 'tactics' })];

  it('returns everything for "all"', () => {
    expect(filterByGroup(items, 'all')).toBe(items);
  });

  it('keeps only the selected group', () => {
    expect(filterByGroup(items, 'tactics').map((item) => item.key)).toEqual(['b']);
  });
});

describe('sortForGallery', () => {
  it('puts unlocks first, then rarer tiers, then shallower ladder steps', () => {
    const items = [
      progress({ key: 'locked-gold', tier: 'gold' }),
      progress({ key: 'locked-bronze', tier: 'bronze' }),
      progress({ key: 'unlocked', unlocked: true, tier: 'legendary' }),
      progress({ key: 'ladder-50', tier: 'bronze', threshold: 50 }),
    ];
    expect(sortForGallery(items).map((item) => item.key)).toEqual([
      'unlocked',
      'locked-bronze',
      'ladder-50',
      'locked-gold',
    ]);
  });

  it('does not mutate the input', () => {
    const items = [progress({ key: 'b', tier: 'gold' }), progress({ key: 'a' })];
    sortForGallery(items);
    expect(items.map((item) => item.key)).toEqual(['b', 'a']);
  });
});

describe('progressPercent', () => {
  it('rounds a 0..1 ratio into a bar width', () => {
    expect(progressPercent(0.5)).toBe(50);
    expect(progressPercent(0.1234)).toBe(12);
  });

  it('clamps out-of-range and non-finite values', () => {
    expect(progressPercent(1.7)).toBe(100);
    expect(progressPercent(-0.2)).toBe(0);
    expect(progressPercent(Number.NaN)).toBe(0);
  });
});

describe('formatCounter', () => {
  it('shows value over threshold', () => {
    expect(formatCounter(12, 50)).toBe('12 / 50');
  });

  it('never shows progress past the goal', () => {
    expect(formatCounter(75, 50)).toBe('50 / 50');
  });
});

describe('formatUnlockedAt', () => {
  it('reads a timestamp as a local date', () => {
    const iso = '2026-10-23T18:30:00';
    expect(formatUnlockedAt(iso)).toBe(new Date(iso).toLocaleDateString());
  });

  it('treats missing or unreadable stamps as blank', () => {
    expect(formatUnlockedAt(null)).toBe('');
    expect(formatUnlockedAt(undefined)).toBe('');
    expect(formatUnlockedAt('not-a-date')).toBe('');
  });
});

describe('newestUnlocked', () => {
  const items = [
    progress({ key: 'old', unlocked: true, unlocked_at: '2026-01-01T00:00:00' }),
    progress({ key: 'new', unlocked: true, unlocked_at: '2026-02-01T00:00:00' }),
    progress({ key: 'no-stamp', unlocked: true, unlocked_at: null }),
    progress({ key: 'locked' }),
  ];

  it('orders most recent first and skips tiles without a stamp', () => {
    expect(newestUnlocked(items, 5).map((item) => item.key)).toEqual(['new', 'old']);
  });

  it('honours the limit', () => {
    expect(newestUnlocked(items, 1).map((item) => item.key)).toEqual(['new']);
  });
});

describe('mergeQueue', () => {
  const first = entry({ key: 'a' });
  const second = entry({ key: 'b' });

  it('appends only unlocks the queue does not already hold', () => {
    expect(mergeQueue([first], [first, second]).map((item) => item.key)).toEqual(['a', 'b']);
  });

  it('returns the same array when there is nothing new', () => {
    const current = [first];
    expect(mergeQueue(current, [first])).toBe(current);
    expect(mergeQueue(current, [])).toBe(current);
    expect(mergeQueue(current, null)).toBe(current);
    expect(mergeQueue(current, undefined)).toBe(current);
  });
});
