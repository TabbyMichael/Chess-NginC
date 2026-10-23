/**
 * Haptic feedback (Vibration API). Each game event maps to a pattern whose
 * strength suits the moment. Guarded for unsupported browsers (desktop Safari
 * ignores `navigator.vibrate`) and honours prefers-reduced-motion.
 */

export type HapticName =
  | 'select'
  | 'move'
  | 'castle'
  | 'capture'
  | 'promotion'
  | 'check'
  | 'checkmate'
  | 'gameEnd'
  | 'error'
  | 'achievement';

const PATTERNS: Record<HapticName, number | number[]> = {
  select: 8,
  move: 14,
  castle: [18, 40, 18],
  // Stronger captures scale via `captureIntensity` (a plain pulse here).
  capture: 28,
  promotion: [20, 55, 22],
  check: [30, 45, 30],
  checkmate: [55, 90, 45, 130],
  gameEnd: [40, 60, 40],
  error: 32,
  achievement: [35, 60, 35, 60, 60],
};

function reducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function vibrate(name: HapticName, intensity = 0.6): void {
  if (typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') return;
  if (reducedMotion()) return;
  const base = PATTERNS[name];
  // Scale durations with intensity (0.5x .. 1.5x); patterns keep their rhythm.
  const factor = 0.5 + Math.max(0, Math.min(1, intensity));
  const pattern = Array.isArray(base)
    ? base.map((ms, i) => (i % 2 === 0 ? Math.round(ms * factor) : ms))
    : Math.round(base * factor);
  try {
    navigator.vibrate(pattern);
  } catch {
    /* some browsers throw when not user-gesture initiated; ignore */
  }
}
