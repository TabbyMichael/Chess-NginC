/**
 * Narration text for one reviewed ply (REVIEW-009).
 *
 * The review payload is written for the eye: `Nf3`, `O-O`, `32 cp`, em-dashes.
 * Read aloud untouched that becomes "en eff three" and "thirty two cee pee", so
 * every fact is put into English here — one testable place, no engine calls and
 * no network, exactly like the rest of `lib/`.
 */
import type { ReviewMoveResponse } from './api-types';
import { winPctFor } from './review';

const PIECE_WORDS: Record<string, string> = {
  N: 'knight',
  B: 'bishop',
  R: 'rook',
  Q: 'queen',
  K: 'king',
};

/** Short spoken verdict for an engine grade, appended to the move itself. */
const QUALITY_CLAUSE: Record<string, string> = {
  brilliant: ', a brilliant sacrifice',
  best: ', exactly what the engine wanted',
  excellent: ', excellent',
  good: ', solid',
  inaccuracy: ', a step in the wrong direction',
  mistake: ', a mistake',
  blunder: ', a blunder',
};

/**
 * SAN in words: 'Nf3' → 'knight to f3', 'exd5' → 'the e-pawn takes d5',
 * 'O-O' → 'castles kingside', 'Qxh7#' → 'queen takes h7, checkmate'.
 *
 * Disambiguation is kept as a place ('knight from b to d2') because a reader
 * cannot hear the difference between two knights otherwise. Anything that does
 * not match a known shape is returned as written rather than guessed at.
 */
export function speakableSan(san: string): string {
  const raw = san.trim();
  if (!raw) return 'a move';
  const suffix = raw.includes('#') ? ', checkmate' : raw.includes('+') ? ', check' : '';
  const body = raw.replace(/[+#]/g, '').replace(/[?!]/g, '');

  const castled = body.replace(/-/g, '').toUpperCase();
  if (castled === 'OOO') return `castles queenside${suffix}`;
  if (castled === 'OO') return `castles kingside${suffix}`;

  const promoted = body.match(/^(?:([a-h])x)?([a-h]\d)=([NBRQ])$/);
  if (promoted) {
    const [, file, square, piece] = promoted;
    const lead = file ? `pawn takes ${square}, promoting to` : `pawn to ${square} promotes to`;
    return `${lead} ${PIECE_WORDS[piece]}${suffix}`;
  }

  const pieceMove = body.match(/^([NBRQK])([a-h]?[1-8]?)(x?)([a-h]\d)$/);
  if (pieceMove) {
    const [, piece, from, capture, to] = pieceMove;
    const word = PIECE_WORDS[piece] ?? 'piece';
    const origin = from ? ` from ${from}` : '';
    return `${word}${origin} ${capture ? 'takes' : 'to'} ${to}${suffix}`;
  }

  const pawnTake = body.match(/^([a-h])x([a-h]\d)$/);
  if (pawnTake) return `the ${pawnTake[1]}-pawn takes ${pawnTake[2]}${suffix}`;

  if (/^[a-h]\d$/.test(body)) return `pawn to ${body}${suffix}`;
  return `${body}${suffix}`;
}

/** Tidy board notation into something worth hearing. */
export function speakable(text: string): string {
  return text
    .replace(/[\u2014\u2013]/g, ',') // a dash becomes a breath, not a beep
    .replace(/\bcp\b/g, 'points')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * The sentence(s) spoken for one ply: what was played, how it is graded, which
 * opening the position belongs to, what it is worth, and the coach's line.
 */
export function narratePly(move: ReviewMoveResponse | null): string {
  if (!move) return '';
  const side = move.color === 'w' ? 'White' : 'Black';
  const clause = QUALITY_CLAUSE[move.quality] ?? '';
  const sentences: string[] = [
    `Move ${move.move_number}: ${side} plays ${speakableSan(move.san)}${clause}.`,
  ];

  if (move.opening_name) {
    const family = move.opening_name.split(':')[0].trim();
    sentences.push(
      move.in_book
        ? `This is ${move.opening_name}.`
        : `Play has left the book, still inside the ${family}.`,
    );
  }

  // Spoken from the mover's side: naming the player leaves nothing to infer.
  const expectancy = winPctFor(move.win_pct, move.color);
  if (expectancy != null) {
    sentences.push(`${side}'s win expectancy here is ${expectancy} percent.`);
  }

  const coaching = speakable(move.explanation ?? '');
  if (coaching) sentences.push(coaching);
  return sentences.join(' ');
}
