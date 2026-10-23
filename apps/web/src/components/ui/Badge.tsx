/**
 * Achievement tile: consistent lucide iconography, explicit unlocked/locked
 * state, no decorative effects. `icon` is a ReactNode so pages control the
 * shared icon set.
 */
import type { ReactNode } from 'react';
import { clsx } from 'clsx';

export type BadgeProps = {
  name: string;
  desc: string;
  icon: ReactNode;
  unlocked?: boolean;
  className?: string;
};

export function Badge({ name, desc, icon, unlocked = false, className }: BadgeProps) {
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
      <span className="achievement-state">{unlocked ? 'Unlocked' : 'Locked'}</span>
    </div>
  );
}
