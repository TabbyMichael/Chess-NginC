/** Review helper tests: grade metadata, eval formatting, graph geometry,
 * opening naming and the win-expectancy point of view (REVIEW-008). */
import { describe, expect, it } from 'vitest';

import type { ReviewMoveResponse } from './api-types';
import {
  QUALITY_META,
  QUALITY_ORDER,
  formatEval,
  graphCoordinates,
  graphPath,
  openingAverage,
  openingFamily,
  qualityMeta,
  uciSquares,
  winPctFor,
} from './review';

describe('quality metadata', () => {
  it('covers every grade exactly once, best to worst', () => {
    expect(QUALITY_ORDER).toHaveLength(7);
    expect(QUALITY_ORDER.every((q) => QUALITY_META[q].label !== undefined)).toBe(true);
    const ranks = QUALITY_ORDER.map((q) => QUALITY_META[q].rank);
    expect([...ranks].sort((a, b) => b - a)).toEqual(ranks);
  });

  it('falls back to the neutral grade for unknown strings', () => {
    expect(qualityMeta('nonsense').css).toBe('good');
  });
});

describe('formatEval', () => {
  it('renders centipawns as signed pawns', () => {
    expect(formatEval(310)).toBe('+3.1');
    expect(formatEval(-45)).toBe('-0.5');
    expect(formatEval(0)).toBe('0.0');
    expect(formatEval(20)).toBe('+0.2');
  });

  it('prefers mate distances and keeps the sign meaningful', () => {
    expect(formatEval(0, 2)).toBe('M2');
    expect(formatEval(0, -1)).toBe('M1');
  });
});

describe('graphCoordinates', () => {
  it('maps white advantage up and black advantage down', () => {
    const [top, bottom] = graphCoordinates(
      [
        { ply: 1, cp: 800, mate: null },
        { ply: 2, cp: -800, mate: null },
      ],
      100,
      50,
      1000,
    );
    expect(top.y).toBeLessThan(25);
    expect(bottom.y).toBeGreaterThan(25);
    expect(top.x).toBe(0);
    expect(bottom.x).toBeCloseTo(100);
  });

  it('clamps extreme evaluations to the box', () => {
    const [point] = graphCoordinates([{ ply: 1, cp: 99999, mate: null }], 10, 10, 1000);
    expect(point.y).toBe(0);
    expect(point.cp).toBe(1000);
  });

  it('treats a mate score as the decisive edge', () => {
    const [point] = graphCoordinates([{ ply: 1, cp: 0, mate: 2 }], 10, 10, 1000);
    expect(point.y).toBe(0);
  });

  it('handles empty and single-point graphs', () => {
    expect(graphCoordinates([], 100, 50)).toEqual([]);
    const [only] = graphCoordinates([{ ply: 1, cp: 0, mate: null }], 100, 50);
    expect(only).toMatchObject({ x: 0, y: 25 });
    expect(graphPath([only])).toBe('0.0,25.0');
  });
});

describe('uciSquares', () => {
  it('splits a UCI move into from/to squares', () => {
    expect(uciSquares('e2e4')).toEqual({ from: 'e2', to: 'e4' });
    expect(uciSquares('e7e8q')).toEqual({ from: 'e7', to: 'e8' });
    expect(uciSquares('xx')).toBeNull();
  });
});

describe('winPctFor', () => {
  it('keeps a white perspective untouched', () => {
    expect(winPctFor(76, 'w')).toBe(76);
  });

  it('mirrors the number for the player on black', () => {
    expect(winPctFor(76, 'b')).toBe(24);
  });

  it('stays unknown when there is no expectancy to read', () => {
    expect(winPctFor(null, 'w')).toBeNull();
    expect(winPctFor(undefined, 'b')).toBeNull();
  });
});

describe('openingFamily', () => {
  it('takes the name before the first variation separator', () => {
    expect(openingFamily('Sicilian Defense: Najdorf Variation, English Attack')).toBe(
      'Sicilian Defense',
    );
  });

  it('is the whole name when there is no separator, and empty when unnamed', () => {
    expect(openingFamily('Ruy Lopez')).toBe('Ruy Lopez');
    expect(openingFamily(null)).toBe('');
    expect(openingFamily(undefined)).toBe('');
  });
});

describe('openingAverage', () => {
  function move(name: string | null, pct: number | null): ReviewMoveResponse {
    return { opening_name: name, win_pct: pct } as ReviewMoveResponse;
  }

  it('means the plies that belong to the named opening', () => {
    const moves = [
      move('Ruy Lopez', 70),
      move('Ruy Lopez: Morphy Defense', 60),
      move('French Defense', 20),
    ];
    expect(openingAverage(moves, 'Ruy Lopez', 'w')).toBe(65);
  });

  it('reads the average from the same side the panel speaks for', () => {
    const moves = [move('Ruy Lopez', 70), move('Ruy Lopez', 60)];
    expect(openingAverage(moves, 'Ruy Lopez', 'b')).toBe(35);
  });

  it('is null with no family or no numbers to average', () => {
    expect(openingAverage([move('Ruy Lopez', 70)], '', 'w')).toBeNull();
    expect(openingAverage([move('Ruy Lopez', null)], 'Ruy Lopez', 'w')).toBeNull();
    expect(openingAverage([], 'Ruy Lopez', 'w')).toBeNull();
  });

  it('ignores unnamed plies rather than guessing an opening', () => {
    expect(openingAverage([move(null, 50)], 'Ruy Lopez', 'w')).toBeNull();
  });
});
