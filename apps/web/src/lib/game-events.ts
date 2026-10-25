/**
 * Game-event dispatcher: turns a chess move into the right feedback (sound +
 * haptics) with an intensity matched to the moment — a quiet pawn slide feels
 * lighter than capturing a queen, which is lighter than checkmate. Reads the
 * user's sound/haptics preferences and stays silent when they are off.
 *
 * Classification is display-only and derived from chess.js on the *previous*
 * position; the server already accepted the move before we are called.
 */
import { Chess } from 'chess.js';

import { getPref } from './settings';
import { playSound, type SoundName } from './sound';
import { vibrate, type HapticName } from './haptics';

export type GameEventName =
  | 'select'
  | 'move'
  | 'castle'
  | 'capture'
  | 'promotion'
  | 'check'
  | 'checkmate'
  | 'gameEnd'
  | 'error'
  | 'achievement';

export type ClassifiedMove = { event: GameEventName; intensity: number };

// Material value drives capture intensity (bigger prey = heavier thud).
const CAPTURE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9 };

function uciToMove(uci: string): { from: string; to: string; promotion?: string } {
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const promotion = uci.length > 4 ? uci.slice(4, 5) : undefined;
  return promotion ? { from, to, promotion } : { from, to };
}

/**
 * Classify a successful move. `preFen` is the position before the move; `uci`
 * the move applied; `status` the server's post-move game status. Priority:
 * checkmate > check > castle > promotion > capture > plain move.
 */
export function classifyMove(preFen: string, uci: string, status: string): ClassifiedMove {
  try {
    const game = new Chess(preFen);
    const mv = game.move(uciToMove(uci));
    const flags = mv.flags ?? '';
    const castle = flags.includes('k') || flags.includes('q');
    const promotion = flags.includes('p');
    const captured = mv.captured as string | undefined;
    // After the move, the side to move is the opponent: check/mate are theirs.
    const isMate = status === 'checkmate' || game.isCheckmate();
    const isCheck = game.inCheck();

    if (isMate) return { event: 'checkmate', intensity: 1 };
    if (isCheck) return { event: 'check', intensity: 0.8 };
    if (castle) return { event: 'castle', intensity: 0.55 };
    if (promotion) return { event: 'promotion', intensity: 0.75 };
    if (captured) {
      const value = CAPTURE_VALUE[captured] ?? 3; // 1..9 → 0.4..1.0
      return { event: 'capture', intensity: 0.4 + (value / 9) * 0.6 };
    }
    return { event: 'move', intensity: 0.35 };
  } catch {
    // Unparsable/illegal here (shouldn't happen post-acceptance): soft tap.
    return { event: 'move', intensity: 0.35 };
  }
}

/** Play sound + haptics for a classified event, honouring preferences. */
export function fire(event: GameEventName, intensity = 0.6): void {
  if (getPref('sound')) playSound(event as SoundName, intensity);
  if (getPref('haptics')) vibrate(event as HapticName, intensity);
}

/** Convenience: classify a move and play it. */
export function emitMove(preFen: string, uci: string, status: string): void {
  const { event, intensity } = classifyMove(preFen, uci, status);
  fire(event, intensity);
}

/** Post-move FEN (display-only), falling back to the input on any error. */
function advance(fen: string, uci: string): string {
  try {
    const game = new Chess(fen);
    game.move(uciToMove(uci));
    return game.fen();
  } catch {
    return fen;
  }
}

/**
 * Play feedback for every ply added since the last snapshot, walking the FEN
 * forward so each move is classified against the position it was made from.
 * A single player move, an auto-engine reply, or an online broadcast all
 * funnel through here uniformly. Returns the last event played (or null).
 */
export function emitMoveSequence(
  preFen: string,
  ucis: string[],
  finalStatus: string,
): GameEventName | null {
  let fen = preFen;
  let last: GameEventName | null = null;
  ucis.forEach((uci, i) => {
    const isLast = i === ucis.length - 1;
    const { event, intensity } = classifyMove(fen, uci, isLast ? finalStatus : 'active');
    fire(event, intensity);
    last = event;
    fen = advance(fen, uci);
  });
  return last;
}

export function emitSelect(): void {
  fire('select', 0.2);
}

export function emitError(): void {
  fire('error', 0.5);
}

export function emitAchievement(): void {
  fire('achievement', 1);
}

/**
 * A game just transitioned to a terminal status. If the last move was mate it
 * already played the checkmate sound; otherwise (resign/draw/stalemate) play
 * the neutral game-end cadence so endings always feel resolved.
 */
export function emitGameEnd(status: string, lastWasMate: boolean): void {
  if (status === 'active' || lastWasMate) return;
  fire('gameEnd', 0.8);
}
