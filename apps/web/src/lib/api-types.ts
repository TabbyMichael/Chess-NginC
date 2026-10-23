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

export type GameMode = 'local' | 'computer';

export type GameStatus = 'active' | 'checkmate' | 'stalemate' | 'draw' | 'resigned' | 'abandoned';

export interface MoveResponse {
  uci: string;
  san: string;
  move_number: number;
}

export interface GameResponse {
  id: number;
  mode: GameMode;
  status: GameStatus;
  fen: string;
  version: number;
  moves: MoveResponse[];
}

export interface CreateGameRequest {
  mode?: GameMode;
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
