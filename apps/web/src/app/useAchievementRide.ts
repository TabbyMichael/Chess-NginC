/**
 * Ride hook: game and review responses carry the achievements unlocked by that
 * very action (`unlocked_achievements`, ACH-006). Pages mount this on their
 * response object and nothing else — the provider deduplicates, so polling and
 * re-renders can never stack a second toast for the same unlock.
 *
 * Unlike `useAchievements`, this one tolerates a missing provider: celebration
 * is presentation layered on top of the board, and a page rendered without it
 * must still play the game.
 */
import { useContext, useEffect, useMemo } from 'react';

import { AchievementContext } from './achievement-context';
import type { AchievementResponse } from '../lib/api-types';

export type UnlocksCarrier = {
  unlocked_achievements?: AchievementResponse[] | null;
};

export function useAchievementRide(source: UnlocksCarrier | null | undefined): void {
  const context = useContext(AchievementContext);
  const items = useMemo(() => source?.unlocked_achievements ?? [], [source]);

  useEffect(() => {
    if (items.length > 0) context?.celebrate(items);
  }, [items, context]);
}
