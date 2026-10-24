import { describe, expect, it } from 'vitest';

import type { TrainingThemeProgress } from './api-types';
import { levelChip, progressPct, themeIdea, themeOrder, uciFromTo } from './training';

function progress(overrides: Partial<TrainingThemeProgress> = {}): TrainingThemeProgress {
  return { label: 'X', solved: 0, attempts: 0, level: 1, pct: 0, ...overrides };
}

describe('levelChip', () => {
  it('names the three rungs', () => {
    expect(levelChip(1)).toBe('Easy');
    expect(levelChip(2)).toBe('Medium');
    expect(levelChip(3)).toBe('Hard');
  });

  it('clamps out-of-range levels to the ends', () => {
    expect(levelChip(0)).toBe('Easy');
    expect(levelChip(9)).toBe('Hard');
  });
});

describe('progressPct', () => {
  it('is zero when nothing has been attempted', () => {
    expect(progressPct(0, 0)).toBe(0);
  });

  it('is a rounded percentage of solved over attempts', () => {
    expect(progressPct(1, 4)).toBe(25);
    expect(progressPct(3, 4)).toBe(75);
    expect(progressPct(1, 3)).toBe(33);
  });
});

describe('themeOrder', () => {
  it('sorts the curated themes into their canonical order', () => {
    const themes = {
      endgame: progress(),
      mate: progress(),
      fork: progress(),
      hanging: progress(),
      pin: progress(),
      skewer: progress(),
      discovered: progress(),
      backrank: progress(),
      sequence: progress(),
    };
    expect(themeOrder(themes)).toEqual([
      'mate',
      'hanging',
      'fork',
      'pin',
      'skewer',
      'discovered',
      'backrank',
      'endgame',
      'sequence',
    ]);
  });

  it('keeps only the themes present and appends unknown ones, sorted', () => {
    const themes = { zebra: progress(), fork: progress(), mate: progress() };
    expect(themeOrder(themes)).toEqual(['mate', 'fork', 'zebra']);
  });
});

describe('themeIdea', () => {
  it('gives a teaching line for a known theme', () => {
    expect(themeIdea('mate')).not.toBe('');
    expect(themeIdea('skewer')).not.toBe('');
    expect(themeIdea('discovered')).not.toBe('');
    expect(themeIdea('sequence')).not.toBe('');
  });

  it('returns an empty string for an unknown theme', () => {
    expect(themeIdea('nope')).toBe('');
  });
});

describe('uciFromTo', () => {
  it('splits a plain move into its two squares', () => {
    expect(uciFromTo('e2e4')).toEqual({ from: 'e2', to: 'e4' });
  });

  it('ignores the promotion suffix', () => {
    expect(uciFromTo('e7e8q')).toEqual({ from: 'e7', to: 'e8' });
  });

  it('returns null for a too-short string', () => {
    expect(uciFromTo('e2e')).toBeNull();
  });
});
