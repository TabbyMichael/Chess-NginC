/**
 * Celebration toast (ACH-007): one unlocked achievement at a time, with a
 * confetti burst and a rarity-coloured ring. It auto-dismisses and can be
 * closed early; either way the caller acknowledges the unlock so a reload
 * never replays the same moment.
 */
import { useEffect, type CSSProperties } from 'react';
import { X } from 'lucide-react';

import { TIER_LABELS } from '../lib/achievements';
import { DEFAULT_GROUP_ICON, TIER_ICONS } from '../lib/achievement-icons';
import type { AchievementResponse } from '../lib/api-types';

export const CELEBRATION_MS = 6000;

const CONFETTI_COLORS = ['#f2b134', '#2f9e6f', '#3b6fe0', '#d4453c', '#8e5cd9'];

// Fixed burst geometry: computed once so every render animates identically.
const CONFETTI: CSSProperties[] = Array.from({ length: 18 }, (_, index) => ({
  left: `${3 + index * 5.4}%`,
  animationDelay: `${(index % 9) * 0.09}s`,
  background: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
}));

export type AchievementCelebrationProps = {
  items: AchievementResponse[];
  onDismiss: (key: string) => void;
};

export default function AchievementCelebration({ items, onDismiss }: AchievementCelebrationProps) {
  const current = items[0] ?? null;
  // Keyed on the identity of the shown achievement: a new toast re-arms the
  // timer, and re-renders of the same one do not.
  const key = current?.key;

  useEffect(() => {
    if (!key) return;
    const timer = setTimeout(() => onDismiss(key), CELEBRATION_MS);
    return () => clearTimeout(timer);
  }, [key, onDismiss]);

  if (!current) return null;
  // A map lookup (never a factory call) so the icon keeps its identity.
  const Icon = TIER_ICONS[current.tier] ?? DEFAULT_GROUP_ICON;

  return (
    <div className="celebration-host" aria-live="polite">
      <div className={`celebration tier-${current.tier}`} role="status">
        <span className="celebration-confetti" aria-hidden="true">
          {CONFETTI.map((style, index) => (
            <i key={index} style={style} />
          ))}
        </span>
        <span className="celebration-icon" aria-hidden="true">
          <Icon size={22} />
        </span>
        <span className="celebration-copy">
          <span className="celebration-kicker">{`Achievement unlocked · ${TIER_LABELS[current.tier] ?? current.tier}`}</span>
          <strong className="celebration-title">{current.title}</strong>
          <span className="celebration-desc">{current.description}</span>
        </span>
        <button
          type="button"
          className="celebration-close"
          onClick={() => onDismiss(current.key)}
          aria-label={`Dismiss ${current.title}`}
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
