/** Move history list with numbering (WEB-017), empty state included. */
import type { MoveResponse } from '../lib/api-types';

export default function MoveHistory({ moves }: { moves: MoveResponse[] }) {
  if (moves.length === 0) {
    return <p>No moves yet. White to move.</p>;
  }
  const rows: { num: number; white?: string; black?: string }[] = [];
  moves.forEach((m, idx) => {
    if (idx % 2 === 0) rows.push({ num: idx / 2 + 1, white: m.san });
    else rows[rows.length - 1].black = m.san;
  });
  return (
    <ol aria-label="move history" className="moves">
      {rows.map((row) => (
        <li key={row.num}>
          <span className="move-num">{row.num}.</span> <span>{row.white}</span>
          {row.black && (
            <>
              {' '}
              <span>{row.black}</span>
            </>
          )}
        </li>
      ))}
    </ol>
  );
}
