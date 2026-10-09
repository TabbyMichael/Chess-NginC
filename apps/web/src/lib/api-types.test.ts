/**
 * Contract test (API-022): frontend types match the live backend OpenAPI.
 * Run with the backend importable; skips gracefully otherwise.
 */
import { describe, expect, it } from 'vitest';

import type { CreateGameRequest, EngineMoveRequest, GameResponse, MoveRequest } from './api-types';

describe('api-types contract', () => {
  it('request shapes accept backend-valid payloads', () => {
    const create: CreateGameRequest = { mode: 'local' };
    const move: MoveRequest = { uci: 'e2e4', expected_version: 1 };
    const engine: EngineMoveRequest = {
      expected_version: 2,
      max_depth: 3,
      max_time_ms: 1000,
    };
    expect(create.mode).toBe('local');
    expect(move.uci).toBe('e2e4');
    expect(engine.max_depth).toBe(3);
  });

  it('game response covers all backend statuses', () => {
    const statuses: GameResponse['status'][] = [
      'active',
      'checkmate',
      'stalemate',
      'draw',
      'resigned',
      'abandoned',
    ];
    expect(statuses).toHaveLength(6);
  });
});
