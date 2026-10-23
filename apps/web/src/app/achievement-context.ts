/**
 * Achievement context object and its shape, kept apart from the provider so
 * `AchievementContext.tsx` (component) and `useAchievements.ts` (hook) can
 * both import it without breaking React Fast Refresh.
 */
import { createContext } from 'react';

import type { AchievementResponse } from '../lib/api-types';

export type AchievementState = {
  /** Celebrations waiting to be shown, oldest first. */
  queue: AchievementResponse[];
  /** Queue unlocks reported by a response ride or a catch-up read. */
  celebrate: (items?: AchievementResponse[] | null) => void;
  /** Acknowledge one celebration: it is removed and never replayed. */
  dismiss: (key: string) => void;
};

export const AchievementContext = createContext<AchievementState | null>(null);
