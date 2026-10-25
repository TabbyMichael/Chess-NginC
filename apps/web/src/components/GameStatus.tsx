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

export default function GameStatusBanner({
  status,
  inCheck,
}: {
  status: Status;
  inCheck: boolean;
}) {
  return (
    <span role="status" aria-live="polite" className={`status-pill ${status}`}>
      {LABELS[status]}
      {status === 'active' && inCheck && ' — check!'}
    </span>
  );
}
