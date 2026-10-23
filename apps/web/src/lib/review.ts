/**
 * Review-page helpers: shared presentation metadata for the seven engine
 * grades plus geometry for the evaluation graph. Pure functions so the page
 * stays declarative and the math is unit-testable.
 */
import type { MoveQuality, ReviewEvalPoint } from './api-types';

export type QualityMeta = {
  /** Short symbol shown in the move list (Chess.com-style glyph). */
  glyph: string;
  /** Accessible label for the badge. */
  label: string;
  /** CSS class suffix: `quality-<suffix>`. */
  css: string;
  /** Rank for sorting/impact: higher = better move. */
  rank: number;
};

export const QUALITY_META: Record<MoveQuality, QualityMeta> = {
  brilliant: { glyph: '!!', label: 'Brilliant', css: 'brilliant', rank: 6 },
  best: { glyph: '★', label: 'Best', css: 'best', rank: 5 },
  excellent: { glyph: '□', label: 'Excellent', css: 'excellent', rank: 4 },
  good: { glyph: '', label: 'Good', css: 'good', rank: 3 },
  inaccuracy: { glyph: '?!', label: 'Inaccuracy', css: 'inaccuracy', rank: 2 },
  mistake: { glyph: '?', label: 'Mistake', css: 'mistake', rank: 1 },
  blunder: { glyph: '??', label: 'Blunder', css: 'blunder', rank: 0 },
};

export const QUALITY_ORDER: MoveQuality[] = [
  'brilliant',
  'best',
  'excellent',
  'good',
  'inaccuracy',
  'mistake',
  'blunder',
];

export function qualityMeta(quality: string): QualityMeta {
  return QUALITY_META[quality as MoveQuality] ?? QUALITY_META.good;
}

/** '+3.1' / '-0.4' / 'M2' / 'M-1' centipawn-mate phrasing. */
export function formatEval(cp: number, mate?: number | null): string {
  if (mate != null && mate !== 0) {
    return mate > 0 ? `M${mate}` : `M${Math.abs(mate)}`;
  }
  const pawns = cp / 100;
  const rounded = Math.abs(pawns) < 0.05 ? 0 : pawns;
  const sign = rounded > 0 ? '+' : '';
  return `${sign}${rounded.toFixed(1)}`;
}

export type GraphPoint = { x: number; y: number; ply: number; cp: number };

/**
 * Map eval-graph points into an SVG box of width × height. The curve is
 * white-perspective: white better climbs toward the top. Mate scores are
 * clamped to the board edge because they dwarf any centipawn value.
 */
export function graphCoordinates(
  points: ReviewEvalPoint[],
  width: number,
  height: number,
  maxCp = 1000,
): GraphPoint[] {
  if (points.length === 0) return [];
  const clamp = (cp: number) => Math.max(-maxCp, Math.min(maxCp, cp));
  const step = points.length === 1 ? 0 : width / (points.length - 1);
  return points.map((p, index) => {
    const cp = p.mate != null ? (p.mate > 0 ? maxCp : -maxCp) : clamp(p.cp);
    return {
      x: step * index,
      // cp=+maxCp → y=0 (white wins), cp=-maxCp → y=height (black wins).
      y: ((maxCp - cp) / (2 * maxCp)) * height,
      ply: p.ply,
      cp,
    };
  });
}

/** Polyline `points` attribute for the graph path. */
export function graphPath(coords: GraphPoint[]): string {
  return coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
}

/** UCI 'e2e4' → { from: 'e2', to: 'e4' } for board highlighting. */
export function uciSquares(uci: string): { from: string; to: string } | null {
  if (uci.length < 4) return null;
  return { from: uci.slice(0, 2), to: uci.slice(2, 4) };
}
