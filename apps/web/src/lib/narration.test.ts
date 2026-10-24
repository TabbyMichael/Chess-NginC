/**
 * Narration text tests (REVIEW-009): board notation and eval shorthand are
 * written for the eye, so the checks here are that they come out as English.
 */
import { describe, expect, it } from 'vitest';

import type { ReviewMoveResponse } from './api-types';
import { narratePly, speakable, speakableSan } from './narration';

describe('speakableSan', () => {
  it.each([
    ['Nf3', 'knight to f3'],
    ['Bb5', 'bishop to b5'],
    ['Rxd8', 'rook takes d8'],
    ['Qxh7#', 'queen takes h7, checkmate'],
    ['Bb5+', 'bishop to b5, check'],
    ['Kh1', 'king to h1'],
    ['e4', 'pawn to e4'],
    ['exd5', 'the e-pawn takes d5'],
    ['g8=Q', 'pawn to g8 promotes to queen'],
    ['dxe8=N', 'pawn takes e8, promoting to knight'],
    ['O-O', 'castles kingside'],
    ['O-O-O', 'castles queenside'],
    ['Nbd2', 'knight from b to d2'],
    ['Rhe1', 'rook from h to e1'],
    ['fxc8=B+', 'pawn takes c8, promoting to bishop, check'],
    ['', 'a move'],
  ])('reads %s as %s', (san, expected) => {
    expect(speakableSan(san)).toBe(expected);
  });

  it('keeps an unrecognised token as written rather than guessing', () => {
    expect(speakableSan('e4-e5')).toBe('e4-e5');
  });

  it('drops annotation glyphs but keeps the verdict punctuation', () => {
    expect(speakableSan('Nf3!')).toBe('knight to f3');
    expect(speakableSan('Qh6??')).toBe('queen to h6');
  });
});

describe('speakable', () => {
  it('says centipawns as points', () => {
    expect(speakable('25 cp under the best line')).toBe('25 points under the best line');
  });

  it('turns a dash into a breath', () => {
    expect(speakable('the bishop — trapped — is lost')).toBe('the bishop , trapped , is lost');
  });

  it('collapses the whitespace a PGN-style line leaves behind', () => {
    expect(speakable('  rook   to e1 \n then  ')).toBe('rook to e1 then');
  });
});

function ply(overrides: Partial<ReviewMoveResponse> = {}): ReviewMoveResponse {
  return {
    ply: 7,
    move_number: 4,
    uci: 'g1f3',
    san: 'Nf3',
    pre_fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    color: 'w',
    quality: 'best',
    centipawn_loss: 0,
    best_uci: 'g1f3',
    eval_cp: 30,
    eval_mate: null,
    explanation: 'Nf3 is exactly what the engine wants.',
    opening_eco: 'C40',
    opening_name: "King's Knight Opening",
    in_book: true,
    win_pct: 56,
    ...overrides,
  };
}

describe('narratePly', () => {
  it('says the move, the grade and the coach line in one breath', () => {
    const text = narratePly(ply());
    expect(text).toContain('Move 4: White plays knight to f3, exactly what the engine wanted.');
    expect(text).toContain("This is King's Knight Opening.");
    expect(text).toContain("White's win expectancy here is 56 percent.");
    expect(text).toContain('Nf3 is exactly what the engine wants.');
  });

  it('speaks for the player who moved, not for White by default', () => {
    const black = ply({ color: 'b', san: 'e5', uci: 'e7e5', win_pct: 56 });
    expect(narratePly(black)).toContain("Black's win expectancy here is 44 percent.");
  });

  it('leaves out the opening clause when nothing is named', () => {
    const text = narratePly(ply({ opening_name: null, opening_eco: null, in_book: false }));
    expect(text).not.toMatch(/opening|book|unknown/i);
  });

  it('says play has left the book but names the opening that got there', () => {
    const text = narratePly(
      ply({ in_book: false, opening_name: 'Ruy Lopez: Morphy Defense, Modern Line' }),
    );
    expect(text).toContain('Play has left the book, still inside the Ruy Lopez.');
    expect(text).not.toContain('This is Ruy Lopez');
  });

  it('omits the expectancy sentence when the ply has no evaluation', () => {
    const text = narratePly(ply({ win_pct: null }));
    expect(text).not.toMatch(/percent/);
    expect(text).toContain('knight to f3');
  });

  it('reads the eval shorthand in the coach line aloud', () => {
    const text = narratePly(
      ply({ quality: 'mistake', explanation: 'e5 is 25 cp under the best line — develop instead' }),
    );
    expect(text).toContain('a mistake');
    expect(text).toContain('25 points under the best line , develop instead');
  });

  it('is empty for no ply at all', () => {
    expect(narratePly(null)).toBe('');
  });
});
