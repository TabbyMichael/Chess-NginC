/**
 * Plays move feedback for a live game. Watches the game snapshot and fires the
 * sound/haptic sequence for any plies added since the previous render — so the
 * player's own move, the auto-engine reply, and an online broadcast all feel
 * identical. The first snapshot after load is silent (no replaying history).
 */
import { useEffect, useRef } from 'react';

import { emitGameEnd, emitMoveSequence } from './game-events';
import type { GameResponse } from './api-types';

export function useGameFeedback(game: GameResponse | null): void {
  const prev = useRef<{ fen: string; count: number } | null>(null);

  useEffect(() => {
    if (!game) {
      prev.current = null;
      return;
    }
    const before = prev.current;
    prev.current = { fen: game.fen, count: game.moves.length };
    if (!before) return; // initial load: don't replay stored moves

    if (game.moves.length > before.count) {
      const newUcis = game.moves.slice(before.count).map((m) => m.uci);
      const last = emitMoveSequence(before.fen, newUcis, game.status);
      emitGameEnd(game.status, last === 'checkmate');
    } else if (game.moves.length < before.count) {
      // Undo/reset: realign without sound.
      return;
    } else if (game.status !== 'active') {
      // Terminal status reached without a new ply (e.g. resignation).
      emitGameEnd(game.status, false);
    }
  }, [game]);
}
