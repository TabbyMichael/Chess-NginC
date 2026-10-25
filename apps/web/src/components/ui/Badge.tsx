/**
 * Achievement tile: consistent lucide iconography, explicit unlocked/locked
 * state, no decorative effects. `icon` is a ReactNode so pages control the
 * shared icon set.
 *
 * `progress` (0..1) and `detail` describe how close a locked tile is; both are
 * optional so plain unlocked tiles stay as compact as they were.
 */
import type { ReactNode } from 'react';
import { clsx } from 'clsx';

export type BadgeProps = {
  name: string;
  desc: string;
  icon: ReactNode;
  unlocked?: boolean;
  className?: string;
  /** 0..1 completion toward the goal; renders a bar under the description. */
  progress?: number;
  /** Short counter line, e.g. '12 / 50'. */
  detail?: string;
};

export function Badge({
  name,
  desc,
  icon,
  unlocked = false,
  className,
  progress,
  detail,
}: BadgeProps) {
  const pct =
    progress === undefined ? null : Math.max(0, Math.min(100, Math.round(progress * 100)));
  return (
    <div
      className={clsx('achievement', unlocked ? 'unlocked' : 'locked', className)}
      title={unlocked ? `${name} — unlocked` : `${name} — locked`}
    >
      <span className="achievement-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="achievement-name">{name}</span>
      <p className="achievement-desc">{desc}</p>
      {pct !== null && (
        <span className="achievement-progress" role="img" aria-label={`${pct}% toward the goal`}>
          <span className="achievement-progress-fill" style={{ width: `${pct}%` }} />
        </span>
      )}
      {detail && <span className="achievement-counter">{detail}</span>}
      <span className="achievement-state">{unlocked ? 'Unlocked' : 'Locked'}</span>
    </div>
  );
}
