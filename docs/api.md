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
| `POST /auth/forgot-password` | — | `200` neutral message always. Body: `{email}`. Rate-limited |
| `POST /auth/reset-password` | — | `200` on success; `400` invalid/expired token or weak password. Body: `{token, password}`. Revokes all sessions |
| `POST /auth/google` | — | `200` + sets session. Body: `{credential}` (Google ID token, verified server-side). `404` when unconfigured, `401` on bad token |
| `POST /auth/logout` | 🔒¹ | `204`, revokes session, clears cookies |
| `GET /auth/me` | 🔒 | `200 {id, email}` |

¹ Logout is idempotent: always `204` + clears cookies, even without a session.

## Games (all 🔒)

| Method & Path | Description |
|---------------|-------------|
| `POST /games` | Create game. Body: `{mode: "local" \| "computer"}` → `201`; `422` for `"online"` (online games come from the lobby queue) |
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

## Online play (all 🔒, online-plan Phases 1–3)

| Method & Path | Description |
|---------------|-------------|
| `POST /online/queue` | Join the match queue. `200 {status: "queued"}` or `{status: "matched", game_id, color}` when an opponent is waiting. Duplicate queueing is idempotent |
| `DELETE /online/queue` | Cancel a pending slot; always `204` |
| `GET /online/queue` | `{status: "idle" \| "queued" \| "matched"(+game_id, color)}` — safe to poll |
| `GET /online/games` | Caller's online games from **either color seat**, newest first |
| `GET /online/games/{id}` | Participant-scoped fetch; `404` for strangers (never `403`) |
| `POST /online/games/{id}/moves` | Body: `{uci, expected_version}`. Turn-checked server-side (`422 "It is not your turn"`); both seats earn move points |
| `POST /online/games/{id}/resign` | Resigning seat scores `loss`, opponent `win` |
| `POST /online/games/{id}/draw-claim` | Position-based (fifty-move/repetition/stalemate/insufficient material); both seats score `draw` |

Rate limits: online move POSTs are capped per user per minute
(`MOVE_RATE_LIMIT_PER_MINUTE`, default 60; `429` beyond). The legacy
`/games/{id}/*` routes refuse online games with `422`.

### WebSocket `/api/v1/online/ws?game_id={id}`

Cookie-authenticated upgrade; closed before accept with `4400` (no game id),
`4401` (no session), `4403` (not a participant / bad origin). JSON frames
`{type, payload}` ≤ 4 KB, ≤ 10 msgs/s (else `1008`). Client → server:
`move`, `resign`, `draw_claim`, `ping`. Server → client: `game_state` (full
authoritative `GameResponse` broadcast to both seats), `opponent_joined`,
`opponent_left`, `pong`, `error` (sender only). The socket is a transport —
every action runs through the same service path as REST, and the frontend
falls back to polling when it drops.

## OpenAPI

- Machine schema: `GET /openapi.json` (validated by `tests/test_openapi.py`).
- Frontend types: `apps/web/src/lib/api-types.ts` (API-022; contract-tested).
