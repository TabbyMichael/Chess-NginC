/**
 * Client-side chess helpers. The backend is authoritative for legality and
 * outcomes; these helpers only render positions and preview UX hints.
 * FEN parsing here is display-only — moves are always validated server-side.
 */
import { Chess } from 'chess.js';
import type { Square as ChessJsSquare } from 'chess.js';

export type Square = string; // e.g. 'e4'

export type Piece = {
  kind: 'p' | 'n' | 'b' | 'r' | 'q' | 'k';
  color: 'w' | 'b';
};

export type BoardMap = Map<Square, Piece>;

const FILES = 'abcdefgh';

/** Parse the piece-placement field of a FEN into a square→piece map. */
export function parseFenPlacement(fen: string): BoardMap {
  const board: BoardMap = new Map();
  const placement = fen.split(' ')[0];
  const ranks = placement.split('/');
  if (ranks.length !== 8) return board;
  ranks.forEach((row, rankIdx) => {
    const rank = 8 - rankIdx;
    let fileIdx = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        fileIdx += parseInt(ch, 10);
      } else {
        const square = `${FILES[fileIdx]}${rank}`;
        board.set(square, {
          kind: ch.toLowerCase() as Piece['kind'],
          color: ch === ch.toUpperCase() ? 'w' : 'b',
        });
        fileIdx += 1;
      }
    }
  });
  return board;
}

/** Side to move from a FEN string ('w' | 'b'). */
export function sideToMove(fen: string): 'w' | 'b' {
  return fen.split(' ')[1] === 'b' ? 'b' : 'w';
}

/**
 * Squares the piece on `square` could legally move to — a UX preview only
 * (dots on empty targets, rings on captures). Returns [] for unparsable
 * positions or when no friendly piece is on the square; the server remains
 * the sole authority on whether a submitted move is legal.
 */
export function legalTargets(fen: string, square: string): string[] {
  try {
    const game = new Chess(fen);
    return game.moves({ square: square as ChessJsSquare, verbose: true }).map((m) => m.to);
  } catch {
    return [];
  }
}

/** All 64 squares in display order (rank 8 → 1). */
export function allSquares(): Square[] {
  const squares: Square[] = [];
  for (let rank = 8; rank >= 1; rank -= 1) {
    for (let file = 0; file < 8; file += 1) {
      squares.push(`${FILES[file]}${rank}`);
    }
  }
  return squares;
}

/** Square color for the checkerboard pattern (a1 and h8 are dark). */
export function isLightSquare(square: Square): boolean {
  const file = FILES.indexOf(square[0]);
  const rank = parseInt(square[1], 10);
  return (file + rank) % 2 === 0;
}

/** Standard starting position piece counts per color. */
const START_COUNTS: Record<Piece['kind'], number> = { p: 8, n: 2, b: 2, r: 2, q: 1, k: 1 };

/** Standard piece values for material counts (kings excluded). */
const PIECE_VALUES: Record<Piece['kind'], number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };

/**
 * Material balance from surviving pieces (display-only): positive means
 * White is ahead, negative means Black is ahead, pawns = 1.
 */
export function materialBalance(fen: string): number {
  const board = parseFenPlacement(fen);
  let balance = 0;
  for (const piece of board.values()) {
    const value = PIECE_VALUES[piece.kind];
    balance += piece.color === 'w' ? value : -value;
  }
  return balance;
}

/**
 * Captured pieces per side, derived by diffing the starting material against
 * the current position (WEB-018). Display-only; the server owns game state.
 */
export function capturedPieces(fen: string): {
  capturedByWhite: Piece['kind'][];
  capturedByBlack: Piece['kind'][];
} {
  const board = parseFenPlacement(fen);
  const present: Record<Piece['color'], Record<Piece['kind'], number>> = {
    w: { p: 0, n: 0, b: 0, r: 0, q: 0, k: 0 },
    b: { p: 0, n: 0, b: 0, r: 0, q: 0, k: 0 },
  };
  for (const piece of board.values()) present[piece.color][piece.kind] += 1;

  const missing = (color: Piece['color']): Piece['kind'][] => {
    const out: Piece['kind'][] = [];
    for (const kind of ['q', 'r', 'b', 'n', 'p'] as const) {
      const lost = START_COUNTS[kind] - present[color][kind];
      for (let i = 0; i < lost; i += 1) out.push(kind);
    }
    return out;
  };

  return {
    // Black pieces that vanished were captured by White, and vice versa.
    capturedByWhite: missing('b'),
    capturedByBlack: missing('w'),
  };
}
