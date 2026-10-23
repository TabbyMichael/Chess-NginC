/**
 * Evaluation graph for the review page: one point per ply, white-perspective
 * (above the midline = White is better). Points are clickable so the board can
 * jump to that ply; keyboard-accessible via buttons in the move list.
 */
import type { ReviewEvalPoint } from '../lib/api-types';
import { formatEval, graphCoordinates, graphPath } from '../lib/review';

const WIDTH = 600;
const HEIGHT = 140;

type Props = {
  points: ReviewEvalPoint[];
  activePly: number | null;
  onSelectPly: (ply: number) => void;
};

export default function EvalGraph({ points, activePly, onSelectPly }: Props) {
  const coords = graphCoordinates(points, WIDTH, HEIGHT);
  if (coords.length === 0) {
    return <p className="u-muted">No evaluation graph available for this game.</p>;
  }
  const mid = HEIGHT / 2;
  return (
    <div className="eval-graph">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        height={HEIGHT}
        role="img"
        aria-label="Evaluation advantage over the game (white perspective)"
        preserveAspectRatio="none"
      >
        <line x1="0" y1={mid} x2={WIDTH} y2={mid} className="graph-zero" strokeWidth="1" />
        <polyline points={graphPath(coords)} className="graph-line" fill="none" strokeWidth="2" />
        {coords.map((c) => (
          <circle
            key={c.ply}
            cx={c.x}
            cy={c.y}
            r={c.ply === activePly ? 5 : 3}
            className={`graph-dot${c.ply === activePly ? ' active' : ''}`}
            onClick={() => onSelectPly(c.ply)}
          >
            <title>{`Move ${c.ply}: ${formatEval(c.cp)}`}</title>
          </circle>
        ))}
      </svg>
      <p className="graph-legend">
        <span>Black advantage</span>
        <span>Equal</span>
        <span>White advantage</span>
      </p>
    </div>
  );
}
