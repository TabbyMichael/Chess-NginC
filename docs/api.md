# API Reference (API-020)

> Base URL: `/api/v1`. All responses are JSON. Errors use the envelope
> `{ "detail": "<message>" }` (SEC-016/SEC-017: no hashes, tokens, or traces).

## Conventions

- **Auth:** session cookie `session_token` (HttpOnly, SameSite=Lax). Endpoints
  marked 🔒 require it; otherwise `401 {"detail": "Not authenticated"}`.
- **CSRF:** state-changing endpoints require a same-origin `Origin`/`Referer`
  (see SEC-008); cross-origin POSTs get `403`.
- **Rate limits:** auth endpoints allow 10 req/min per IP (`429` when exceeded).
- **Ownership:** games are scoped to the caller; foreign/unknown ids return
  `404` (indistinguishable, no enumeration).

## Status codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Successful reads and actions |
| 201 | Created | Registration, game creation |
| 204 | No Content | Logout (cookies cleared) |
| 400 | Bad Request | Invalid email/password/mode |
| 401 | Unauthorized | Missing/expired session, bad credentials |
| 403 | Forbidden | Cross-origin state-changing request |
| 404 | Not Found | Unknown id or foreign-owner resource |
| 409 | Conflict | Stale `expected_version`, action on finished game |
| 422 | Unprocessable Content | Illegal/unparsable move, bad draw claim |
| 429 | Too Many Requests | Auth rate limit exceeded |

## Auth

| Method & Path | Auth | Description |
|---------------|------|-------------|
| `POST /auth/register` | — | `201` + sets session. Body: `{email, password}` |
| `POST /auth/login` | — | `200` + sets session. Generic 401 message |
| `POST /auth/logout` | 🔒¹ | `204`, revokes session, clears cookies |
| `GET /auth/me` | 🔒 | `200 {id, email}` |

¹ Logout is idempotent: always `204` + clears cookies, even without a session.

## Games (all 🔒)

| Method & Path | Description |
|---------------|-------------|
| `POST /games` | Create game. Body: `{mode: "local" \| "computer"}` → `201` |
| `GET /games` | List caller's games, newest first |
| `GET /games/{id}` | One game + ordered moves; `404` if foreign |
| `POST /games/{id}/moves` | Body: `{uci, expected_version}`. Validates legality (422), version (409), terminal sync |
| `POST /games/{id}/undo` | Body: `{expected_version}`. Restores FEN, drops last move row, bumps version |
| `POST /games/{id}/resign` | Marks `resigned`; `409` if already finished |
| `POST /games/{id}/draw-claim` | `422` unless the position supports a draw claim |
| `POST /games/{id}/engine-move` | Computer games only. Body: `{expected_version, max_depth? ≤6, max_time_ms? ≤3000}`. Records `engine_runs` row |

### Move flow

1. Client sends `{uci, expected_version}` where `expected_version` is the
   `version` from its last `GameResponse`.
2. Server validates legality via python-chess, persists the move row, bumps
   `version += 1`, and derives terminal status (checkmate/stalemate/draw).
3. Client retries on `409` by re-fetching and replaying intent.

## OpenAPI

- Machine schema: `GET /openapi.json` (validated by `tests/test_openapi.py`).
- Frontend types: `apps/web/src/lib/api-types.ts` (API-022; contract-tested).
