/**
 * A single chess piece drawn from the vendored Merida artwork (lib/pieces).
 * Both colors are solid fills, which Unicode glyphs cannot guarantee.
 */
import { PIECE_ART } from '../lib/pieces';

type Props = {
  /** Piece kind: k, q, r, b, n, p. */
  kind: string;
  color: 'w' | 'b';
  className?: string;
};

export default function PieceIcon({ kind, color, className }: Props) {
  const art = PIECE_ART[color === 'w' ? kind.toUpperCase() : kind.toLowerCase()];
  if (!art) return null;
  return (
    <svg
      className={className}
      viewBox="0 0 45 45"
      aria-hidden="true"
      focusable="false"
      dangerouslySetInnerHTML={{ __html: art }}
    />
  );
}
