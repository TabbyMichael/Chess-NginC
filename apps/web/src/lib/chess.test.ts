import { describe, expect, it } from 'vitest';

import {
  allSquares,
  capturedPieces,
  isLightSquare,
  legalTargets,
  materialBalance,
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

describe('capturedPieces (WEB-018)', () => {
  it('reports nothing captured in the starting position', () => {
    const { capturedByWhite, capturedByBlack } = capturedPieces(START_FEN);
    expect(capturedByWhite).toEqual([]);
    expect(capturedByBlack).toEqual([]);
  });

  it('credits White for a captured black pawn', () => {
    const { capturedByWhite, capturedByBlack } = capturedPieces(AFTER_CAPTURE);
    expect(capturedByWhite).toEqual(['p']);
    expect(capturedByBlack).toEqual([]);
  });

  it('counts multiple and mixed captured pieces', () => {
    // Black is missing queen + both rooks; White is missing one knight.
    const fen = '1nb1kbn1/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1';
    const { capturedByBlack, capturedByWhite } = capturedPieces(fen);
    // The tray holds kinds; PlayerInfo renders each in the captured side's color.
    expect(capturedByWhite).toEqual(['q', 'r', 'r']);
    expect(capturedByBlack).toEqual(['n']);
  });

  it('never reports a captured king', () => {
    const fen = '8/8/8/8/8/8/8/4K3 w - - 0 1';
    const { capturedByBlack } = capturedPieces(fen);
    expect(capturedByBlack).not.toContain('k');
  });
});

describe('materialBalance', () => {
  it('is level at the starting position', () => {
    expect(materialBalance(START_FEN)).toBe(0);
  });

  it('is positive when White is ahead by a pawn', () => {
    // Black is missing the d7 pawn only.
    expect(materialBalance('rnbqkbnr/ppp1pppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')).toBe(1);
  });

  it('is negative when Black is ahead', () => {
    // White is missing the b1 knight only.
    expect(materialBalance('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR b KQkq - 0 1')).toBe(-3);
  });

  it('ignores kings', () => {
    expect(materialBalance('4k3/8/8/8/8/8/8/4K3 w - - 0 1')).toBe(0);
  });
});

describe('legalTargets', () => {
  it('lists the two one- and two-square pawn pushes from the start', () => {
    expect(legalTargets(START_FEN, 'e2').sort()).toEqual(['e3', 'e4']);
  });

  it('lists knight jumps', () => {
    expect(legalTargets(START_FEN, 'g1').sort()).toEqual(['f3', 'h3']);
  });

  it('includes captures the piece can legally make', () => {
    // White pawn on d6 can capture the black pawn on e7.
    const fen = 'rnbqkbnr/pppppppp/3P4/8/8/8/PPP1PPPP/RNBQKBNR w KQkq - 0 3';
    expect(legalTargets(fen, 'd6')).toContain('e7');
  });

  it('returns nothing for an empty or enemy-occupied square', () => {
    expect(legalTargets(START_FEN, 'e4')).toEqual([]);
    expect(legalTargets(START_FEN, 'e7')).toEqual([]);
  });

  it('returns nothing for a malformed FEN instead of throwing', () => {
    expect(legalTargets('nonsense', 'e2')).toEqual([]);
  });

  it('respects the side to move', () => {
    // After 1.e4 it is Black's move: White's e-pawn has no targets.
    expect(legalTargets(AFTER_CAPTURE, 'e2')).toEqual([]);
  });
});
