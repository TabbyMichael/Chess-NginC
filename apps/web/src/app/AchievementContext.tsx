/**
 * Achievement celebration state (ACH-006/007).
 *
 * Unlocks reach the client in three ways — a game mutation response, a review
 * response, or the private `achievement` socket event — and one more on load:
 * `GET /me/achievements/new` catches anything earned while this tab was closed.
 * The provider owns a single queue so a player never sees the same toast twice
 * in one session, and each dismissal is acknowledged back to the server.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { AchievementContext } from './achievement-context';
import AchievementCelebration from '../components/AchievementCelebration';
import { api } from '../lib/api-client';
import { emitAchievement } from '../lib/game-events';
import { mergeQueue } from '../lib/achievements';
import type { AchievementResponse } from '../lib/api-types';
import { useAuth } from './useAuth';

export function AchievementProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [queue, setQueue] = useState<AchievementResponse[]>([]);
  // Keys already queued since this mount: the ride and the catch-up read can
  // report the same unlock, and neither may produce a second toast for it.
  const shown = useRef<Set<string>>(new Set());

  const celebrate = useCallback((items?: AchievementResponse[] | null) => {
    if (!items || items.length === 0) return;
    const fresh = items.filter((item) => !shown.current.has(item.key));
    if (fresh.length === 0) return;
    fresh.forEach((item) => shown.current.add(item.key));
    setQueue((prev) => mergeQueue(prev, fresh));
    emitAchievement();
  }, []);

  // Lazy catch-up on load; a failure here is decorative and stays silent.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api
      .newAchievements()
      .then((items) => {
        if (!cancelled) celebrate(items);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [user, celebrate]);

  const dismiss = useCallback((key: string) => {
    setQueue((prev) => prev.filter((item) => item.key !== key));
    api.markAchievementsSeen([key]).catch(() => undefined);
  }, []);

  const value = useMemo(() => ({ queue, celebrate, dismiss }), [queue, celebrate, dismiss]);

  return (
    <AchievementContext.Provider value={value}>
      {children}
      <AchievementCelebration items={user ? queue : []} onDismiss={dismiss} />
    </AchievementContext.Provider>
  );
}
