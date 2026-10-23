/**
 * Move history (WEB-017): numbered rows in standard notation with separate
 * white/black columns; the most recent move is highlighted. Empty state
 * included. Scrollable independently of the page.
 */
import { clsx } from 'clsx';
import type { MoveResponse } from '../lib/api-types';

export default function MoveHistory({ moves }: { moves: MoveResponse[] }) {
  if (moves.length === 0) {
    return (
      <div className="empty-state">
        <p>No moves yet. White to move.</p>
      </div>
    );
  }
  const rows: { num: number; white?: string; black?: string }[] = [];
  moves.forEach((m, idx) => {
    if (idx % 2 === 0) rows.push({ num: idx / 2 + 1, white: m.san });
    else rows[rows.length - 1].black = m.san;
  });
  const lastIndex = rows.length - 1;
  const lastIsBlack = Boolean(rows[lastIndex].black);
  return (
    <ol aria-label="move history" className="moves">
      {rows.map((row, idx) => (
        <li key={row.num}>
          <span className="move-num">{row.num}.</span>
          <span className={clsx('move-san', idx === lastIndex && !lastIsBlack && 'latest')}>
            {row.white}
          </span>
          <span className={clsx('move-san', idx === lastIndex && lastIsBlack && 'latest')}>
            {row.black ?? ''}
          </span>
        </li>
      ))}
    </ol>
  );
}
