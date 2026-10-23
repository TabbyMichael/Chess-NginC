/**
 * Move-classification tests: every kind of moment (quiet move, capture of
 * varying size, castle, promotion, check, mate) must map to the right event
 * and an intensity ordered by significance. Pure logic — no audio runs here.
 */
import { describe, expect, it } from 'vitest';

import { classifyMove } from './game-events';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

describe('classifyMove', () => {
  it('reads a quiet pawn slide as a plain move', () => {
    expect(classifyMove(START_FEN, 'e2e4', 'active')).toEqual({ event: 'move', intensity: 0.35 });
  });

  it('scales capture intensity with the material taken', () => {
    // White pawn on d5 takes a black pawn on e6.
    const pawnCapture = 'rnbqkbnr/ppp1pppp/4p3/3P4/8/8/PPP1PPPP/RNBQKBNR w KQkq e6 0 3';
    // White knight on f3 takes a hanging black queen on d4.
    const queenCapture = 'rnb1kbnr/pppp1ppp/8/4p3/3q4/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 4';
    const low = classifyMove(pawnCapture, 'd5e6', 'active');
    const high = classifyMove(queenCapture, 'f3d4', 'active');
    expect(low).toEqual({ event: 'capture', intensity: expect.closeTo(0.4 + (1 / 9) * 0.6, 6) });
    expect(high).toEqual({ event: 'capture', intensity: expect.closeTo(1, 6) });
    expect(high.intensity).toBeGreaterThan(low.intensity);
  });

  it('classifies kingside castling as a castle', () => {
    // Reachable position after 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.Nf3-side develops…:
    // White's king and rook home, knight out — O-O is legal.
    const fen = 'r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4';
    expect(classifyMove(fen, 'e1g1', 'active').event).toBe('castle');
  });

  it('classifies a promotion ahead of a plain move', () => {
    // b7→b8 with the black king far on h1: promotion without check.
    const fen = '8/1P6/8/8/8/8/8/K6k w - - 0 1';
    expect(classifyMove(fen, 'b7b8q', 'active').event).toBe('promotion');
  });

  it('classifies a checking move as check', () => {
    // Rook lift Rd1+ along the open file: quiet move, but it checks.
    const fen = '3r2k1/8/8/8/8/8/8/3RK3 w - - 0 1';
    const result = classifyMove(fen, 'd1d8', 'active');
    expect(result.event).toBe('check');
    expect(result.intensity).toBeGreaterThan(0.55);
  });

  it('ranks a real mate as checkmate with full intensity', () => {
    // Classic fool's mate: 1.f3 e5 2.g4 Qh4#.
    const preMove = 'rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 3';
    expect(classifyMove(preMove, 'd8h4', 'checkmate')).toEqual({
      event: 'checkmate',
      intensity: 1,
    });
    // The server's terminal status wins even for a quiet-looking final ply.
    expect(classifyMove(START_FEN, 'e2e4', 'checkmate').event).toBe('checkmate');
  });

  it('falls back to a soft move for an illegal or unparsable input', () => {
    expect(classifyMove(START_FEN, 'e2e5', 'active')).toEqual({ event: 'move', intensity: 0.35 });
    expect(classifyMove('nonsense', 'e2e4', 'active').event).toBe('move');
  });
});
