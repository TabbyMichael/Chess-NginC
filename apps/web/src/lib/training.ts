/**
 * Pure helpers for the Learn page (LEARN-002/003): the display-order of skill
 * cards, the ramp chip text, progress maths and the small UCI/square glue. No
 * React and no API — everything here is a deterministic function of its inputs
 * so it can be unit-tested in isolation. The server owns the verdict; these
 * only turn its numbers into what the page draws.
 */
import type { TrainingThemeProgress } from './api-types';

/** Curated skill order on the Learn grid; matches the backend THEME_ORDER. */
const THEME_SEQUENCE = ['mate', 'hanging', 'fork', 'pin', 'backrank', 'endgame'] as const;

/** One teaching line per theme, shown under the card title. */
const THEME_IDEAS: Record<string, string> = {
  mate: 'Finish the king in one move.',
  hanging: 'Take what is undefended — and leave yours guarded.',
  fork: 'One piece, two targets at once.',
  pin: 'A piece that dares not move.',
  backrank: 'Give your king a square to escape to.',
  endgame: 'Promote a pawn and march the king forward.',
  missed: 'The move you missed in one of your own games.',
};

const LEVEL_CHIPS = ['Easy', 'Medium', 'Hard'];

/** The ramp chip for a level (1..3); out-of-range values clamp to the ends. */
export function levelChip(level: number): string {
  const index = Math.min(LEVEL_CHIPS.length - 1, Math.max(0, level - 1));
  return LEVEL_CHIPS[index];
}

/** Completion percent (0..100) of a theme from its solved/total progress. */
export function progressPct(solved: number, attempts: number): number {
  if (attempts <= 0) return 0;
  return Math.round((solved / attempts) * 100);
}

/**
 * The theme keys in display order: the curated sequence first, then any theme
 * the server added that we do not know, sorted alphabetically so the grid is
 * still deterministic rather than at the mercy of object key order.
 */
export function themeOrder(themes: Record<string, TrainingThemeProgress>): string[] {
  const keys = Object.keys(themes);
  const known = THEME_SEQUENCE.filter((theme) => keys.includes(theme));
  const rest = keys.filter(
    (theme) => !THEME_SEQUENCE.includes(theme as (typeof THEME_SEQUENCE)[number]),
  );
  return [...known, ...rest.sort()];
}

/** A short one-line idea for a theme; falls back to an empty string. */
export function themeIdea(theme: string): string {
  return THEME_IDEAS[theme] ?? '';
}

/** Split a UCI move into its two squares for board highlighting. */
export function uciFromTo(uci: string): { from: string; to: string } | null {
  if (uci.length < 4) return null;
  return { from: uci.slice(0, 2), to: uci.slice(2, 4) };
}
