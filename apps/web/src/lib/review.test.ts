/** Review helper tests: grade metadata, eval formatting, graph geometry. */
import { describe, expect, it } from 'vitest';

import {
  QUALITY_META,
  QUALITY_ORDER,
  formatEval,
  graphCoordinates,
  graphPath,
  qualityMeta,
  uciSquares,
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
