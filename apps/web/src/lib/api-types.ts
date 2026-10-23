/**
 * Frontend API types (API-022). Generated from the backend OpenAPI schema
 * (`GET /openapi.json`); hand-synced until codegen is automated.
 * @see docs/api.md for endpoint documentation.
 */

export interface UserResponse {
  id: number;
  email: string;
  points: number;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export type LoginRequest = RegisterRequest;

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
}

export interface GoogleLoginRequest {
  credential: string;
}

export interface MessageResponse {
  message: string;
}

export interface ErrorResponse {
  detail: string;
}

export type GameMode = 'local' | 'computer' | 'online';

export type GameStatus = 'active' | 'checkmate' | 'stalemate' | 'draw' | 'resigned' | 'abandoned';

export interface MoveResponse {
  uci: string;
  san: string;
  move_number: number;
}

/** Rarity bands of the achievement catalog (ACH-001). */
export type AchievementTier = 'bronze' | 'silver' | 'gold' | 'diamond' | 'legendary';

/** One catalog entry (ACH-005). */
export interface AchievementResponse {
  key: string;
  title: string;
  description: string;
  metric: string;
  threshold: number;
  tier: AchievementTier;
  group: string;
}

/** A catalog entry as seen by one player: progress plus unlock state. */
export interface AchievementProgressResponse extends AchievementResponse {
  value: number;
  unlocked: boolean;
  /** 0..1 toward the threshold. */
  progress: number;
  unlocked_at?: string | null;
}

export interface AchievementListResponse {
  total: number;
  unlocked: number;
  items: AchievementProgressResponse[];
}

export interface GameResponse {
  id: number;
  mode: GameMode;
  status: GameStatus;
  fen: string;
  version: number;
  moves: MoveResponse[];
  /** Color seats exist only on online games (online-plan §12). */
  white_user_id?: number | null;
  black_user_id?: number | null;
  /** Achievements earned by this very action; reads and peer broadcasts are empty. */
  unlocked_achievements?: AchievementResponse[];
}

export type QueueStatus = 'idle' | 'queued' | 'matched';

export interface QueueResponse {
  status: QueueStatus;
  game_id?: number | null;
  /** 'w' or 'b' when matched. */
  color?: string | null;
}

export interface CreateGameRequest {
  /** 'online' games are created by the lobby queue, never by this request. */
  mode?: Exclude<GameMode, 'online'>;
}

export interface MoveRequest {
  uci: string;
  expected_version: number;
}

export interface VersionRequest {
  expected_version: number;
}

export interface EngineMoveRequest {
  expected_version: number;
  max_depth?: number | null;
  max_time_ms?: number | null;
}

/** Move grades assigned by the post-game engine review (REVIEW-002). */
export type MoveQuality =
  'brilliant' | 'best' | 'excellent' | 'good' | 'inaccuracy' | 'mistake' | 'blunder';

export interface ReviewRequest {
  /** Re-run the engine even when a stored review exists. */
  force?: boolean;
}

export interface ReviewMoveResponse {
  ply: number;
  move_number: number;
  uci: string;
  san: string;
  /** Position the move was played from: the board to show for this ply. */
  pre_fen: string;
  color: 'w' | 'b';
  quality: MoveQuality;
  centipawn_loss: number;
  best_uci: string;
  /** Evaluation after the ply, centipawns from the mover's perspective. */
  eval_cp: number;
  eval_mate?: number | null;
  explanation: string;
}

export interface ReviewEvalPoint {
  ply: number;
  /** Centipawns from WHITE's perspective (graph is always white-up). */
  cp: number;
  mate?: number | null;
}

export interface ReviewImprovement {
  ply: number;
  san: string;
  color: 'w' | 'b';
  best_uci: string;
  loss_cp: number;
}

export interface ReviewSummary {
  ply_count: number;
  accuracy: Record<string, number>;
}

export interface ReviewResponse {
  id: number;
  game_id: number;
  status: 'completed' | 'failed';
  provider: string;
  depth: number;
  hero_color: 'w' | 'b';
  error?: string | null;
  summary: ReviewSummary;
  counts: Record<string, number>;
  moves: ReviewMoveResponse[];
  eval_graph: ReviewEvalPoint[];
  improvements: ReviewImprovement[];
  /** Analysing a game is itself an achievement milestone (ACH-006). */
  unlocked_achievements?: AchievementResponse[];
}
