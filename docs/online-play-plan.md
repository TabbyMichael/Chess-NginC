# Online Play — Implementation Plan

> Status: **planned, not started.** This document is decision-complete: an
> implementer should not need to make architecture choices, only write code.
> Everything referenced below exists today unless marked "new".

## 1. Product definition

Two signed-in humans play each other on separate devices, in real time, on the
same board.

- One player is White, one is Black (random assignment at game start).
- The server is the sole authority for legality, turns, and results — exactly
  like computer games today, but "Black" is a person instead of the engine.
- Moves, clock-free for v1. No time controls, no drag-reconnect drama, no
  chat. (v2 items are listed in §10.)
- Both players earn points from the existing ledger for playing and for the
  result (chess.com-style), see §7.
- Out of scope for v1: rating (Elo), spectators, rematches, resuming after a
  server restart mid-game is best-effort only (state lives in Postgres, so the
  game survives; only the live socket pairing must be re-established).

## 2. Architecture decision

**Server-authoritative WebSocket messages over the modular monolith.**
FastAPI already supports `WebSocket` routes; Postgres stays the source of
truth; the socket only carries events ("your opponent moved"), never state.

Rejected alternatives (do not revisit casually):

- *Polling REST every second* — simplest, but wasteful and laggy; acceptable
  only as a degradation path (the client keeps "sync via REST" on WS failure).
- *Peer-to-peer / WebRTC* — client moves would need trust or duplicated
  validation; breaks the "server owns outcomes" boundary in
  `docs/architecture.md`.
- *Separate realtime service* — the app is deliberately one deployable; a
  second service adds an ops story we do not have yet.

Single-container assumption: the API replica count stays at 1 (compose
today). Both players' sockets live in one process, so an in-memory hub is
correct. If we ever scale beyond one replica, add Redis pub/sub (§10).

## 3. Data model

### 3.1 `games` table changes (migration `a1c7e4f9b2d6`, online_players)

The current `games.user_id` column means "the account that owns this game".
Online games have two owners, so:

- Add `white_user_id: int | NULL` and `black_user_id: int | NULL`
  (`ForeignKey("users.id")`, both indexed). Keep `user_id` for
  local/computer games; for online games set `user_id = white_user_id` so
  existing repository queries (which all filter by `user_id`) keep working
  for White, and add the pair columns as the authority for online games.
- Add `GameMode.ONLINE = "online"` to `app/games/domain.py` (string value
  stored in the `mode` column — no schema change needed for the mode itself).
- Do NOT add status values; reuse `active / checkmate / stalemate / draw /
  resigned / abandoned`.

### 3.2 New table `online_game_participants` (same migration)

Actually needed for the roster/queue? No — v1 pairing is done via the queue
(§5) and stored directly on `games`. Skip this table. (Recorded so future
readers know it was considered.)

### 3.3 Points ledger

`point_awards` already has a unique constraint on `(game_id, reason,
move_number)`. Result awards have `move_number = NULL`; Postgres treats NULLs
as distinct, so dedupe currently relies on the "award only on the
active→terminal transition" guard in `_sync_status`. That guard plus
`resign`/`draw-claim` requiring `_require_active` is sufficient and already
tested for computer games — online games reuse it. No schema change.

## 4. Domain + service layer

New module `app/games/online_service.py` (do not grow `service.py` further):

```python
# All functions take (db, ...) and raise the existing GameNotFoundError /
# GameFinishedError / IllegalMoveRequestError from app/games/errors.py.

def create_online_game(db, white_id: int, black_id: int) -> GameRow
    # mode='online', status='active', fen=STARTING_FEN, version=1,
    # user_id=white_id, white_user_id=white_id, black_user_id=black_id

def submit_online_move(db, game_id, player_id, uci, expected_version) -> GameDetail
    # 1. load game; mode must be 'online'
    # 2. player_id must be white_user_id or black_user_id  (else GameNotFoundError
    #    — SEC-016: never reveal the game exists to strangers)
    # 3. side-to-move from rules.fen must equal the caller's color  (else
    #    IllegalMoveRequestError "It is not your turn")
    # 4. reuse ChessRules + GameRepository + optimistic version guard exactly
    #    like submit_move(); award 'move' points for BOTH players
    # 5. _sync_status-style terminal handling (shared helper), awarding
    #    'win'/'loss'/'draw' to both sides

def resign_online_game(db, game_id, player_id) -> GameDetail
    # status='resigned'; the RESIGNING player gets 'loss', the opponent 'win'

def claim_online_draw(db, game_id, player_id) -> GameDetail
    # v1: position-based only (fifty-moves/repetition/stalemate/insufficient,
    # the same predicates as claim_draw); both players get 'draw'
```

Reuse, don't duplicate: extract the rules-application + move-storage block of
`service.submit_move` into a private helper shared by both services. The move
points rules constant becomes `POINT_RULES = {"move": 1, "win": 10, "draw": 5,
"loss": 3}` for online games too — **both** players earn per-move points.

Turn ownership detail: `_award_points` today credits `game.user_id` only.
Generalize it to `_award_points(db, user_id, game, reason, move_number=None)`
and call it once per player. The unique slot constraint continues to protect
undo/replay farming (online games have no undo in v1 — see §6).

## 5. Matchmaking (the "lobby")

REST + short polling, not sockets, for v1. Matchmaking does not need
sub-second latency and polling degrades gracefully.

- In-process queue in a new `app/games/lobby.py`:
  `deque` of user ids + a ` threading.Lock`, reset on process start (lost on
  restart — fine for v1, users just re-queue).
- `POST /api/v1/online/queue` → `{status: "queued"}` or
  `{status: "matched", game_id, color}`. If a different user is already
  waiting, pop them, `create_online_game(...)`, return the game id to *both*
  calls (the matched pair is assigned random colors via `random.choice`).
- `DELETE /api/v1/online/queue` → leave the queue.
- `GET /api/v1/online/queue` → `{status: "queued"|"idle"|"in_game", game_id?}`
  (used after page reloads).
- Duplicate-queue guard: a user already queued, or with an unfinished online
  game, gets the existing state instead of a second slot.
- Poll interval on the client: 1500 ms; stop polling on match or unmount.

## 6. HTTP + WebSocket API

### 6.1 REST (new router `app/api/v1/online.py`, prefix `/online`, all 🔒)

| Method | Path | Body / Result |
|--------|------|---------------|
| POST | `/online/queue` | → `{status, game_id?, color?}` |
| DELETE | `/online/queue` | → 204 |
| GET | `/online/queue` | → same shape as POST, no side effects |
| POST | `/online/games/{game_id}/moves` | `MoveRequest` → `GameResponse` (409 on stale version, 422 illegal / not-your-turn) |
| POST | `/online/games/{game_id}/resign` | → `GameResponse` |
| POST | `/online/games/{game_id}/draw-claim` | → `GameResponse` (422 if position doesn't support it) |

No undo for online games (your opponent has seen the move; 422 "Undo is not
available in online games").

Reuse `GameResponse`; add to it (new optional fields, backwards compatible):
`white_user_id: int | None`, `black_user_id: int | None`. The frontend needs
"am I White?" — derive from `white_user_id === me.id`, not a server-echoed
per-request flag.

Rate limiting: apply the existing `rate_limit_auth`-style limiter with a new
bucket (`rate_limit_moves`, e.g. 60 moves/min/user) mirroring how auth limits
are wired in `app/api/v1/deps.py`.

### 6.2 WebSocket

`GET /api/v1/online/ws` (upgrade) — one socket per player, joined by game id
query param: `/api/v1/online/ws?game_id=7`.

- **Auth at handshake only**: the browser sends the existing session cookie
  with the upgrade request; validate it with the same session lookup that
  `deps.get_current_user` uses. Reject the socket (close code 4401) if the
  session is invalid or the user is not a participant of `game_id` (4403).
- **Origin check**: reuse the `enforce_same_origin` logic on the upgrade
  request (CSWSRF protection).
- Messages are JSON `{ "type": ..., "payload": ... }`.

Server → client:

```jsonc
{"type": "opponent_joined",  "payload": {"color": "w"}}
{"type": "game_state",       "payload": GameResponse}          // after every change
{"type": "opponent_left",    "payload": {}}                     // socket closed
{"type": "error",            "payload": {"detail": "..."}}
```

Client → server:

```jsonc
{"type": "move", "payload": {"uci": "e2e4", "expected_version": 3}}
{"type": "resign", "payload": {}}
{"type": "draw_claim", "payload": {}}
{"type": "ping", "payload": {}}          // keepalive, reply {"type":"pong"}
```

The server processes client moves through `online_service` (same code path as
REST — the socket is a *transport*, not an authority), then broadcasts
`game_state` to both sockets. A failed move returns `error` to the sender
only; the game is unchanged.

Hub implementation: `app/games/hub.py`, `dict[int, dict[int, WebSocket]]`
(game_id → user_id → socket) guarded by an `asyncio.Lock`. On connect:
register, send current `game_state`, notify the other socket
`opponent_joined`. On disconnect: unregister + `opponent_left`. Broadcast is
best-effort; clients re-fetch `GET /online/games/{id}` (or plain
`GET /games/{id}` since participants own the rows they can see) whenever they
detect a gap (version jump) or after reconnect.

**Keep REST authoritative**: the frontend must work fully with polling-only if
the socket fails (one code path renders state; the socket just accelerates
it).

## 7. Points

- Per move: +1 for each human who moved (slot-deduped as today).
- Result: winner +10, loser +3, draw +5 each — from `POINT_RULES`, unchanged.
- `users.points` updates happen inside `_award_points` as today, once per
  user.
- No rating/Elo in v1 (see §10). The ledger is append-only history; ratings
  later become a *separate* column pair on users, not a repurposed ledger.

## 8. Frontend

New files, all inside the existing shell (`App.tsx` routes, `useAuth`,
`api-client`):

1. `src/pages/LobbyPage.tsx` — route `/lobby`, wrapped in `RequireAuth`.
   "Find a match" button → `queue()`; shows *queued…*' (role=status), cancels
   via `leaveQueue()`; on match → `navigate('/online/:id')`. Also lists the
   user's unfinished online games (`GET /games` filtered by `mode ===
   'online'`).
2. `src/pages/OnlineGamePage.tsx` — route `/online/:id`. Reuse `Chessboard`,
   `MoveHistory`, `GameStatusBanner`, `PlayerInfo` verbatim. Differences from
   `GamePage.tsx`:
   - `boardDisabled = busy || finished || myTurn === false` — pass
     `disabled` into the existing prop; hints disappear automatically because
     `Chessboard` gates on `disabled`.
   - Your color decides orientation later (v1: always White-at-bottom).
   - No auto-engine effect, no undo button.
   - State comes from WS messages; REST fetch on mount and on reconnect.
3. `src/lib/online-ws.ts` — tiny wrapper: open, parse `{type, payload}`,
   reconnect with backoff (1s → 2s → 5s → 10s cap), send queue while
   offline is **not** buffered (reject locally with "not connected").
4. `src/lib/api-client.ts` — add `queueMatch()`, `leaveQueue()`,
   `queueStatus()`, `onlineMove()`, `onlineResign()`, `onlineDrawClaim()`;
   `api-types.ts` — add the matching request/response types and the two new
   optional fields on `GameResponse`; update `api-types.test.ts`.
5. Header: add a `nav-link` "Play online" next to Home (only when logged in).

Update the OpenAPI contract test (`tests/test_openapi.py`) and
`src/lib/api-types.test.ts` in the same PR as the schema changes.

## 9. Security requirements (non-negotiable, mirrors existing docs)

- Session cookie auth on WS upgrade; `HttpOnly`, `SameSite=Lax` as today;
  verify `Origin` header on the upgrade.
- Ownership check on every online call: participant OR 404 (SEC-016 — never
  "forbidden", which confirms the game exists).
- Turn check server-side; client `disabled` prop is UX, not a control.
- Move rate limiting per user; cap WS message size (4 KB) and message rate
  (10/s) — close the socket on repeat violations.
- Never trust client-sent FEN; the server always recomputes from stored state.
- The lobby queue stores ids only — no emails/names exposed to strangers.

## 10. Future phases (do NOT build in v1)

- **v2**: time controls + clocks (server timestamps, abort/grace rules),
  rematch flow, resignation confirm via socket, spectators, chat (rate
  limited), push notifications for queued match found.
- **v3**: Elo/rapid ratings on `users`, rating-based matchmaking (pair users
  within ±100, widening window), seasons/leaderboards fed from
  `point_awards`.
- **Scale-out**: Redis pub/sub behind the hub interface when API replicas > 1
  (sticky sessions are not an option on this compose topology).
- **Persistence of presence**: if "opponent disconnected → auto-win after N
  minutes" is ever added, use a scheduled job, not a socket timer, so restarts
  don't lose it.

## 11. Phased delivery (each phase green before the next)

**Phase 1 — Data + service (no HTTP).**
3.1 migration (add columns + mode value), `online_service.py` functions,
`_award_points` generalization.
Tests: `tests/test_online_service.py` — create/white-move/black-move/
not-your-turn 422/ownership 404/points both players/version conflict/resign
awards win+loss/draw claim. Gates: ruff, mypy, pytest.

**Phase 2 — REST + lobby.**
`online.py` router, `lobby.py` queue, schemas, rate-limit bucket,
OpenAPI test updates.
Tests: `tests/test_online_api.py` — queue/match flow (two `TestClient`s),
move via REST, cross-account 404, undo rejected, duplicate queue guard.

**Phase 3 — WebSocket.**
`hub.py` + WS route + auth/origin handshake + broadcast.
Tests: `TestClient.websocket_connect` (starlette supports it) — handshake
rejects anonymous + strangers, move over WS updates both sockets'
`game_state`, disconnect emits `opponent_left`, ping/pong.

**Phase 4 — Frontend.**
§8 files. Tests: lobby pairing flow with mocked `api` + a fake `WebSocket`
class in `src/test/`; `OnlineGamePage` tests mirror `GamePage.test.tsx`
conventions (aria-label contracts unchanged). Gates: tsc, eslint, vitest,
prettier, build.

**Phase 5 — Docs + deploy.**
`docs/api.md` endpoint table rows, `docs/architecture.md` decisions-log entry
("Online play: server-authoritative WS, single-replica hub"), compose
unchanged (same API container), smoke: two-browser manual playtest, then a
`scripts/smoke-prod.sh` addition.

## 12. Pitfalls checklist (learned from this codebase)

- Alembic: the chain currently ends at `9d4b7a2e61c8`; the new migration's
  `down_revision` must be exactly that.
- `GameRepository` filters by `user_id` — online games must keep `user_id`
  populated (= White) or every query breaks for White; Black is served only
  through the online endpoints.
- `_sync_status` awards result points on the active→terminal transition only;
  keep that single-awards path for online (do not also award in resign).
- FastAPI sync services + WebSocket routes: WS handlers must be `async`;
  run blocking DB work via the existing sync session (do not share the TestClient's
  `db` override assumptions — in prod, create a session per socket message).
- Frontend: `restoreMocks: true` in vitest — every new test must re-spy every
  API method its component touches (including `api.me`).
- The `/games/:id` route currently lets any authenticated user fetch a game
  they own; do not reuse it for Black — Black's fetch must go through an
  online-aware ownership check (participant OR 404).
