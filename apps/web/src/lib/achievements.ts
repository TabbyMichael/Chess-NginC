/**
 * Achievement presentation helpers (ACH-005).
 *
 * Pure and framework-free on purpose: the gallery page, the celebration host
 * and the queue de-duplication all share these rules, and they are the parts
 * worth pinning with tests.
 */
import type {
  AchievementProgressResponse,
  AchievementResponse,
  AchievementTier,
} from './api-types';

export const TIER_ORDER: AchievementTier[] = ['bronze', 'silver', 'gold', 'diamond', 'legendary'];

export const TIER_LABELS: Record<AchievementTier, string> = {
  bronze: 'Bronze',
  silver: 'Silver',
  gold: 'Gold',
  diamond: 'Diamond',
  legendary: 'Legendary',
};

/** Human names for the catalog groups; unknown groups fall back to the raw key. */
export const GROUP_LABELS: Record<string, string> = {
  play: 'Games played',
  result: 'Results',
  points: 'Points',
  tactics: 'Tactics',
  pieces: 'Piece mastery',
  endurance: 'Endurance',
  habit: 'Habits',
  review: 'Review & improvement',
  engine: 'Against the engine',
  mode: 'Ways to play',
  training: 'Training & drills',
};

export function groupLabel(group: string): string {
  return GROUP_LABELS[group] ?? group;
}

/** Catalog order of the groups present, for section headings and filters. */
export function groupsOf(items: AchievementResponse[]): string[] {
  const seen: string[] = [];
  items.forEach((item) => {
    if (!seen.includes(item.group)) seen.push(item.group);
  });
  return seen;
}

export function filterByGroup(
  items: AchievementProgressResponse[],
  group: string,
): AchievementProgressResponse[] {
  if (group === 'all') return items;
  return items.filter((item) => item.group === group);
}

/** Unlock state first, then rarest tier, then the shallowest step of a ladder. */
export function sortForGallery(
  items: AchievementProgressResponse[],
): AchievementProgressResponse[] {
  return [...items].sort((a, b) => {
    if (a.unlocked !== b.unlocked) return a.unlocked ? -1 : 1;
    const tier = TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier);
    if (tier !== 0) return tier;
    if (a.group !== b.group) return a.group.localeCompare(b.group);
    return a.threshold - b.threshold;
  });
}

/** 0..100 for a progress bar; never negative, never over the full bar. */
export function progressPercent(progress: number): number {
  if (!Number.isFinite(progress)) return 0;
  return Math.max(0, Math.min(100, Math.round(progress * 100)));
}

/** "12 / 50" style counter shown on a locked tile. */
export function formatCounter(value: number, threshold: number): string {
  return `${Math.min(value, threshold).toLocaleString()} / ${threshold.toLocaleString()}`;
}

/** Unlock date for the gallery; unparseable or missing stamps read as blank. */
export function formatUnlockedAt(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString();
}

/** Most recently earned first — used by the dashboard strip. */
export function newestUnlocked(
  items: AchievementProgressResponse[],
  limit: number,
): AchievementProgressResponse[] {
  return items
    .filter((item) => item.unlocked && item.unlocked_at)
    .sort((a, b) => String(b.unlocked_at).localeCompare(String(a.unlocked_at)))
    .slice(0, limit);
}

/**
 * Append only achievements the queue does not already hold. Both the response
 * ride and the lazy catch-up read can report the same unlock, so the player
 * must never see the same celebration twice in one session.
 */
export function mergeQueue(
  current: AchievementResponse[],
  incoming: AchievementResponse[] | null | undefined,
): AchievementResponse[] {
  if (!incoming || incoming.length === 0) return current;
  const held = new Set(current.map((item) => item.key));
  const fresh = incoming.filter((item) => !held.has(item.key));
  return fresh.length === 0 ? current : [...current, ...fresh];
}
