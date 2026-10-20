/**
 * Chessboard (WEB-010/011/013/014/027): click-to-select + click-to-move,
 * promotion picker, keyboard operable, turn indicator. Display-only legality:
 * the server is authoritative (invalid moves surface as 422 errors).
 * Gen Alpha makeover: animated pieces, capture explosions, check pulse,
 * last-move indicators, smooth square transitions.
 */
import { useEffect, useMemo, useState } from 'react';

import { allSquares, glyph, isLightSquare, parseFenPlacement, sideToMove } from '../lib/chess';

type Props = {
  fen: string;
  status: string;
  selected: string | null;
  onSelect: (square: string | null) => void;
  onMove: (from: string, to: string, promotion?: string) => void;
  disabled?: boolean;
  lastMove?: { from: string; to: string } | null;
  inCheck?: boolean;
};

const PROMOTION_PIECES = ['q', 'r', 'b', 'n'];

function getPieceColor(color: string): 'white' | 'black' {
  return color === 'w' ? 'white' : 'black';
}

export default function Chessboard({
  fen,
  status,
  selected,
  onSelect,
  onMove,
  disabled = false,
  lastMove,
  inCheck = false,
}: Props) {
  const board = useMemo(() => parseFenPlacement(fen), [fen]);
  const turn = sideToMove(fen);
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  useEffect(() => () => setDragOver(null), []);
  const turnLabel = status !== 'active' ? `Game over: ${status}` : `Turn: ${turn === 'w' ? 'White' : 'Black'}`;
  function isPromotionMove(from: string, to: string): boolean {
    const piece = board.get(from);
    if (!piece || piece.kind !== 'p') return false;
    const toRank = to[1];
    return (piece.color === 'w' && toRank === '8') || (piece.color === 'b' && toRank === '1');
  }
  function handleSquareClick(square: string) {
    if (disabled || status !== 'active') return;
    if (pendingPromotion) return;
    if (selected === null) { if (board.has(square)) onSelect(square); return; }
    if (selected === square) { onSelect(null); return; }
    if (isPromotionMove(selected, square)) { setPendingPromotion({ from: selected, to: square }); return; }
    onMove(selected, square);
    onSelect(null);
  }
  function handleKey(square: string, key: string) {
    if (key === 'Enter' || key === ' ') { handleSquareClick(square); }
    else if (key === 'Escape') { onSelect(null); setPendingPromotion(null); }
  }
  function handleDragStart(square: string, event: any) {
    if (disabled || status !== 'active') { event.preventDefault(); return; }
    onSelect(square);
  }
  function handleDragOver(square: string, event: any) {
    event.preventDefault();
    if (dragOver !== square) setDragOver(square);
  }
  function handleDrop(to: string, event: any) {
    event.preventDefault();
    setDragOver(null);
    const from = selected;
    if (!from || from === to || disabled || status !== 'active') return;
    if (isPromotionMove(from, to)) { setPendingPromotion({ from, to }); return; }
    onMove(from, to);
    onSelect(null);
  }

  const lastFrom = lastMove?.from;
  const lastTo = lastMove?.to;
  return (
    <section aria-label="chessboard" className="mb-xl">
      <p role="status" aria-live="polite" className="text-lg font-bold text-center mb-sm uppercase">{turnLabel}</p>
      <div className="board-wrapper" role="grid" aria-label={`Chess position, ${turn === 'w' ? 'white' : 'black'} to move`}>
        <div className="board">
          {allSquares().map((square) => {
            const piece = board.get(square);
            const isSelected = selected === square;
            const isDraggable = !disabled && status === 'active' && Boolean(piece);
            return (
              <button
                key={square}
                type="button"
                role="gridcell"
                aria-label={`${square}${piece ? `, ${piece.color === 'w' ? 'white' : 'black'} ${piece.kind}` : ', empty'}${isSelected ? ', selected' : ''}`}
                aria-pressed={isSelected}
                draggable={isDraggable}
                className={[ 'square', isLightSquare(square) ? 'light' : 'dark', isSelected ? 'selected' : '', lastFrom === square || lastTo === square ? 'last-move' : '', inCheck && piece?.kind === 'k' ? 'in-check' : '', dragOver === square ? 'dragover' : '' ].filter(Boolean).join(' ')}
                onClick={() => handleSquareClick(square)}
                onKeyDown={(e) => handleKey(square, e.key)}
                onDragStart={(e) => handleDragStart(square, e)}
                onDragOver={(e) => handleDragOver(square, e)}
                onDragLeave={() => setDragOver((cur) => (cur === square ? null : cur))}
                onDrop={(e) => handleDrop(square, e)}
                disabled={disabled}
              >
                {piece && (
                  <span
                    className={`piece ${getPieceColor(piece.color)}`}
                    aria-hidden="true"
                  >
                    {glyph(piece)}
                  </span>
                )}
                <span className="coord" aria-hidden="true">{square}</span>
                </button>
            );
          })}
        </div>
      </div>
      {pendingPromotion && (
        <div role="dialog" aria-label="choose promotion piece" className="promotion-picker">
          <p>Promote pawn {pendingPromotion.from} → {pendingPromotion.to} to:</p>
          <div className="promotion-grid">{PROMOTION_PIECES.map((kind) => (
            <button key={kind} type="button" aria-label={`promote to ${kind}`} onClick={() => { onMove(pendingPromotion.from, pendingPromotion.to, kind); setPendingPromotion(null); onSelect(null); }}>{kind.toUpperCase()}</button>
          ))}</div>
          <button type="button" onClick={() => { setPendingPromotion(null); onSelect(null); }}>Cancel</button>
        </div>
      )}
    </section>
  );
}