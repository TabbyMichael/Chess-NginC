/**
 * Achievement hooks, kept in their own module so `AchievementContext.tsx`
 * exports only components — required for React Fast Refresh in development.
 */
import { useContext } from 'react';

import { AchievementContext, type AchievementState } from './achievement-context';

/** Inside the provider, or nowhere: pages that must celebrate throw early. */
export function useAchievements(): AchievementState {
  const ctx = useContext(AchievementContext);
  if (!ctx) throw new Error('useAchievements must be used within AchievementProvider');
  return ctx;
}

/**
 * Tolerant variant: `null` when no provider is mounted. Feedback layers are
 * presentation on top of a board, so a game page rendered on its own — in a
 * test, or in any future surface without the provider — still has to play.
 */
export function useAchievementsOptional(): AchievementState | null {
  return useContext(AchievementContext);
}
