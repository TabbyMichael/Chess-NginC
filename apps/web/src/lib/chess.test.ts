import { describe, expect, it } from 'vitest';

import {
  allSquares,
  capturedPieces,
  glyph,
  isLightSquare,
  parseFenPlacement,
  sideToMove,
} from './chess';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
// After 1. e4 d5 2. exd5 — White has captured one black pawn.
const AFTER_CAPTURE = 'rnbqkbnr/ppp1pppp/3P4/8/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 3';

describe('parseFenPlacement', () => {
  it('places all 32 starting pieces', () => {
    expect(parseFenPlacement(START_FEN).size).toBe(32);
  });

  it('reads the piece on a square with color', () => {
    const board = parseFenPlacement(START_FEN);
    expect(board.get('e1')).toEqual({ kind: 'k', color: 'w' });
    expect(board.get('d8')).toEqual({ kind: 'q', color: 'b' });
    expect(board.get('e4')).toBeUndefined();
  });

  it('expands empty-square runs', () => {
    const board = parseFenPlacement('8/8/8/4k3/8/8/8/8 w - - 0 1');
    expect(board.size).toBe(1);
    expect(board.get('e5')).toEqual({ kind: 'k', color: 'b' });
  });

  it('returns an empty map for a malformed FEN rather than throwing', () => {
    expect(parseFenPlacement('nonsense').size).toBe(0);
  });
});

describe('sideToMove', () => {
  it('reads the active color', () => {
    expect(sideToMove(START_FEN)).toBe('w');
    expect(sideToMove('8/8/8/8/8/8/8/8 b - - 0 1')).toBe('b');
  });

  it('defaults to white when the field is missing', () => {
    expect(sideToMove('garbage')).toBe('w');
  });
});

describe('allSquares', () => {
  it('lists 64 squares in display order', () => {
    const squares = allSquares();
    expect(squares).toHaveLength(64);
    expect(squares[0]).toBe('a8');
    expect(squares[1]).toBe('b8');
    expect(squares[7]).toBe('h8');
    expect(squares[63]).toBe('h1');
  });

  it('has no duplicates', () => {
    expect(new Set(allSquares()).size).toBe(64);
  });
});

describe('isLightSquare', () => {
  it('treats a1 as dark and h1 as light', () => {
    expect(isLightSquare('a1')).toBe(false);
    expect(isLightSquare('h1')).toBe(true);
  });

  it('alternates along a rank', () => {
    // a8 is light; each step right flips the color.
    expect(isLightSquare('a8')).toBe(true);
    expect(isLightSquare('b8')).toBe(false);
    expect(isLightSquare('h8')).toBe(false);
  });
});

describe('glyph', () => {
  it('distinguishes white from black pieces', () => {
    expect(glyph({ kind: 'k', color: 'w' })).toBe('♔');
    expect(glyph({ kind: 'k', color: 'b' })).toBe('♚');
  });
});

describe('capturedPieces (WEB-018)', () => {
  it('reports nothing captured in the starting position', () => {
    const { capturedByWhite, capturedByBlack } = capturedPieces(START_FEN);
    expect(capturedByWhite).toEqual([]);
    expect(capturedByBlack).toEqual([]);
  });

  it('credits White for a captured black pawn', () => {
    const { capturedByWhite, capturedByBlack } = capturedPieces(AFTER_CAPTURE);
    expect(capturedByWhite).toEqual(['♟']);
    expect(capturedByBlack).toEqual([]);
  });

  it('counts multiple and mixed captured pieces', () => {
    // Black is missing queen + both rooks; White is missing one knight.
    const fen = '1nb1kbn1/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1';
    const { capturedByBlack, capturedByWhite } = capturedPieces(fen);
    // Captured pieces keep their own color glyph.
    expect(capturedByWhite).toEqual(['♛', '♜', '♜']);
    expect(capturedByBlack).toEqual(['♘']);
  });

  it('never reports a captured king', () => {
    const fen = '8/8/8/8/8/8/8/4K3 w - - 0 1';
    const { capturedByBlack } = capturedPieces(fen);
    expect(capturedByBlack).not.toContain('♚');
  });
});
