/** Guards the vendored artwork: solid fills for both colors (no line art). */
import { describe, expect, it } from 'vitest';

import { PIECE_ART } from './pieces';

const KINDS = ['k', 'q', 'r', 'b', 'n', 'p'];

describe('PIECE_ART', () => {
  it('provides every piece in both colors', () => {
    for (const kind of KINDS) {
      expect(PIECE_ART[kind]).toBeTruthy();
      expect(PIECE_ART[kind.toUpperCase()]).toBeTruthy();
    }
    expect(Object.keys(PIECE_ART)).toHaveLength(12);
  });

  it('fills white pieces with the white token and black pieces with the black one', () => {
    for (const kind of KINDS) {
      expect(PIECE_ART[kind.toUpperCase()]).toContain('var(--piece-white)');
      expect(PIECE_ART[kind]).toContain('var(--piece-black)');
    }
  });

  it('draws filled bodies rather than outline-only glyphs', () => {
    // Each piece must carry at least one path with an explicit fill.
    for (const art of Object.values(PIECE_ART)) {
      expect(art).toMatch(/fill="var\(--piece-(white|black)\)"|style="fill:var\(--piece-/);
    }
  });
});
