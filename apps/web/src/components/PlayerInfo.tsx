/**
 * Player bar shown above/below the board: piece color, whose turn it is,
 * the pieces that player has captured, and any material lead. No clocks or
 * identities are invented — the API does not provide them.
 */
import { clsx } from 'clsx';

import type { Piece } from '../lib/chess';
import PieceIcon from './PieceIcon';

type Props = {
  color: 'white' | 'black';
  isTurn: boolean;
  finished: boolean;
  /** Kinds of the pieces this player took (they belong to the other side). */
  captured: Piece['kind'][];
  /** Positive = white ahead; lead is shown for whichever side is ahead. */
  materialBalance: number;
};

export default function PlayerInfo({ color, isTurn, finished, captured, materialBalance }: Props) {
  const lead = color === 'white' ? materialBalance : -materialBalance;
  // The tray shows what this player took, so the pieces belong to the other side.
  const capturedColor = color === 'white' ? 'b' : 'w';
  return (
    <div
      className={clsx('player-bar', isTurn && !finished && 'active-turn')}
      aria-label={`${color} player`}
    >
      <span className={`player-dot ${color}`} aria-hidden="true" />
      <span className="player-name">{color === 'white' ? 'White' : 'Black'}</span>
      {isTurn && !finished && <span className="player-sub">to move</span>}
      {lead > 0 && <span className="material-lead">+{lead}</span>}
      <span className="player-captures" aria-label={`${color} captured ${captured.length} pieces`}>
        {captured.length > 0 ? (
          captured.map((piece, idx) => (
            <PieceIcon key={idx} kind={piece} color={capturedColor} className="captured-piece" />
          ))
        ) : (
          <span className="none">—</span>
        )}
      </span>
    </div>
  );
}
