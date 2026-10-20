/** Status banner: check/checkmate/stalemate/draw/resigned (WEB-015/016). */
import type { GameStatus as Status } from '../lib/api-types';

const LABELS: Record<Status, string> = {
  active: 'Game in progress',
  checkmate: 'Checkmate — game over',
  stalemate: 'Stalemate — draw',
  draw: 'Draw',
  resigned: 'Resigned — game over',
  abandoned: 'Abandoned',
};

const STATUS_VARIANTS: Record<Status, string> = {
  active: 'game-status active',
  checkmate: 'game-status checkmate',
  stalemate: 'game-status stalemate',
  draw: 'game-status draw',
  resigned: 'game-status resigned',
  abandoned: 'game-status resigned',
};

export default function GameStatusBanner({
  status,
  inCheck,
}: {
  status: Status;
  inCheck: boolean;
}) {
  return (
    <div role="status" aria-live="polite" className={STATUS_VARIANTS[status]}>
      <strong>{LABELS[status]}</strong>
      {status === 'active' && inCheck && <span> — check!</span>}
    </div>
  );
}
