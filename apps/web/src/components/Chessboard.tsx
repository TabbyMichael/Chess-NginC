/**
 * Chessboard (WEB-010/011/013/014/027): click-to-select + click-to-move,
 * promotion picker, keyboard operable, turn indicator. Display-only legality:
 * the server is authoritative (invalid moves surface as 422 errors).
 */
import { useEffect, useMemo, useState } from 'react';
import type { DragEvent } from 'react';

import { allSquares, glyph, isLightSquare, parseFenPlacement, sideToMove } from '../lib/chess';

type Props = {
  fen: string;
  status: string;
  selected: string | null;
  onSelect: (square: string | null) => void;
  onMove: (from: string, to: string, promotion?: string) => void;
  disabled?: boolean;
};

const PROMOTION_PIECES = ['q', 'r', 'b', 'n'];

export default function Chessboard({ fen, status, selected, onSelect, onMove, disabled }: Props) {
  const board = useMemo(() => parseFenPlacement(fen), [fen]);
  const turn = sideToMove(fen);
  const [pendingPromotion, setPendingPromotion] = useState<{
    from: string;
    to: string;
  } | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);

  // Cancel any in-flight drag on unmount so stale state never leaks.
  useEffect(() => () => setDragOver(null), []);

  const turnLabel =
    status !== 'active' ? `Game over: ${status}` : `Turn: ${turn === 'w' ? 'White' : 'Black'}`;

  function isPromotionMove(from: string, to: string): boolean {
    const piece = board.get(from);
    if (!piece || piece.kind !== 'p') return false;
    const toRank = to[1];
    return (piece.color === 'w' && toRank === '8') || (piece.color === 'b' && toRank === '1');
  }

  function handleSquareClick(square: string) {
    if (disabled || status !== 'active') return;
    if (pendingPromotion) return; // must pick a piece first
    if (selected === null) {
      if (board.has(square)) onSelect(square);
      return;
    }
    if (selected === square) {
      onSelect(null); // deselect
      return;
    }
    if (isPromotionMove(selected, square)) {
      setPendingPromotion({ from: selected, to: square });
      return;
    }
    onMove(selected, square);
    onSelect(null);
  }

  function handleKey(square: string, key: string) {
    if (key === 'Enter' || key === ' ') {
      handleSquareClick(square);
    } else if (key === 'Escape') {
      onSelect(null);
      setPendingPromotion(null);
    }
  }

  /** Drag start selects the piece; drop on a square attempts the move (WEB-012). */
  function handleDragStart(square: string, event: DragEvent<HTMLButtonElement>) {
    if (disabled || status !== 'active') {
      event.preventDefault();
      return;
    }
    onSelect(square);
  }

  function handleDragOver(square: string, event: DragEvent<HTMLButtonElement>) {
    event.preventDefault(); // allow drop
    if (dragOver !== square) setDragOver(square);
  }

  function handleDrop(to: string, event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragOver(null);
    const from = selected;
    if (!from || from === to || disabled || status !== 'active') return;
    if (isPromotionMove(from, to)) {
      setPendingPromotion({ from, to });
      return;
    }
    onMove(from, to);
    onSelect(null);
  }

  return (
    <section aria-label="chessboard">
      <p role="status" aria-live="polite">
        {turnLabel}
      </p>
      <div
        className="board"
        role="grid"
        aria-label={`Chess position, ${turn === 'w' ? 'white' : 'black'} to move`}
      >
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
              className={[
                'square',
                isLightSquare(square) ? 'light' : 'dark',
                isSelected ? 'selected' : '',
                dragOver === square ? 'dragover' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => handleSquareClick(square)}
              onKeyDown={(e) => handleKey(square, e.key)}
              onDragStart={(e) => handleDragStart(square, e)}
              onDragOver={(e) => handleDragOver(square, e)}
              onDragLeave={() => setDragOver((cur) => (cur === square ? null : cur))}
              onDrop={(e) => handleDrop(square, e)}
              disabled={disabled}
            >
              <span aria-hidden="true" className={piece ? `piece ${piece.color}` : ''}>
                {piece ? glyph(piece) : ''}
              </span>
              <span className="coord" aria-hidden="true">
                {square}
              </span>
            </button>
          );
        })}
      </div>
      {pendingPromotion && (
        <div role="dialog" aria-label="choose promotion piece" className="promotion-picker">
          <p>
            Promote pawn {pendingPromotion.from} → {pendingPromotion.to} to:
          </p>
          {PROMOTION_PIECES.map((kind) => (
            <button
              key={kind}
              type="button"
              aria-label={`promote to ${kind}`}
              onClick={() => {
                onMove(pendingPromotion.from, pendingPromotion.to, kind);
                setPendingPromotion(null);
                onSelect(null);
              }}
            >
              {kind.toUpperCase()}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              setPendingPromotion(null);
              onSelect(null);
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </section>
  );
}
