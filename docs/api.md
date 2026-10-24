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
| 422 | Unprocessable Content | Illegal/unparsable move, bad draw claim, review of an unfinished game |
| 429 | Too Many Requests | Auth rate limit exceeded |
| 503 | Service Unavailable | No Stockfish engine reachable — neither a local binary nor a configured `STOCKFISH_API_KEY` (engine moves / review) |

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
| `POST /games/{id}/engine-move` | Computer games only. Body: `{expected_version, max_depth? ≤6, max_time_ms? ≤3000}`. Answered by real Stockfish — local binary, else the hosted provider when `STOCKFISH_API_KEY` is set (PLAY-001, D7); records an `engine_runs` row; `503` when neither is reachable |
| `POST /games/{id}/review` | Engine review of a finished game (REVIEW-001). Body: `{force?: bool}` |
| `GET /games/{id}/review` | Stored review only — never re-runs the engine (REVIEW-005); `409` when none exists |

### Move flow

1. Client sends `{uci, expected_version}` where `expected_version` is the
   `version` from its last `GameResponse`.
2. Server validates legality via python-chess, persists the move row, bumps
   `version += 1`, and derives terminal status (checkmate/stalemate/draw).
3. Client retries on `409` by re-fetching and replaying intent.

### Response rides

Every mutating game action (and a completed review) returns
`unlocked_achievements: [...]` — the catalog entries that this very action
earned (ACH-006). Reads return an empty list, and an online peer's broadcast
never carries someone else's unlocks.

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
`opponent_left`, `pong`, `error` (sender only), `achievement` (this seat only —
unlocks are never shown to the opponent). The socket is a transport —
every action runs through the same service path as REST, and the frontend
falls back to polling when it drops.

## Game review (all 🔒, REVIEW-001..009)

`POST /games/{id}/review` replays the stored move list through Stockfish with
MultiPV and grades every ply. It runs on **one warm engine process** for the
whole pass (ANL-003), reached through the same provider seam as play — a local
binary if one resolves, otherwise the hosted `stockfishapi.com` provider
(`STOCKFISH_API_KEY`). It is one synchronous pass per game with the review
bounds (depth ≤ 25, ≤ 5 s total — `REVIEW_MAX_*`), and the result is stored per
(game, player), so a second call is free unless `force: true` re-analyses in
place. Both endpoints answer:

| Field | Contents |
|-------|----------|
| `status` | `completed` or `failed` (no engine reachable); `error` carries the reason |
| `provider` | Which engine answered: `stockfish` (local binary) or `stockfish-cloud` (hosted fallback) |
| `hero_color` | The colour this caller played — the review speaks to them |
| `moves[]` | `ply`, `move_number`, `uci`, `san`, `pre_fen`, `color`, `quality`, `centipawn_loss`, `best_uci`, `eval_cp`/`eval_mate` (mover's perspective), `explanation`, plus the derived `opening_eco`, `opening_name`, `in_book`, `win_pct` (White's perspective) |
| `eval_graph[]` | `{ply, cp, mate}` from White's perspective |
| `counts` | Per-grade totals (brilliant/best/excellent/good/inaccuracy/mistake/blunder) |
| `summary` | `ply_count` + `accuracy` per side (0..100) |
| `improvements[]` | The player's own mistakes and blunders with `best_uci` and `loss_cp` |

`quality` comes from centipawn loss against the MultiPV window, with forced-move
and mate-distance rules: `brilliant`, `best`, `excellent`, `good`,
`inaccuracy`, `mistake`, `blunder` (thresholds published in
`app/engine/classifier.py`). A move outside the top-`MultiPV` window is graded
from its **own** post-ply evaluation, not a placeholder (TD-017). `pre_fen` lets
the client render the exact position for each ply without re-deriving it.

Errors: `404` unknown/foreign game, `422` still active or no moves stored,
`409` on `GET` when no review exists yet. A completed review is itself an
achievement milestone, so it can carry `unlocked_achievements`.

### Derived on read, not stored (ANL-004, COA-004, REVIEW-008)

`opening_eco`, `opening_name`, `in_book` and `win_pct` are computed on the way
out of the API by `app/reviews/annotate.py`, from the plies the payload already
holds — the stored JSON is never rewritten, so reviews analysed before these
fields existed gain them on the next read with no re-analysis, and both the
cached `GET` and the fresh `POST` answer identically.

The opening comes from an offline book (`app/openings/`): an EPD-keyed extract
of [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings),
**CC0 / public domain**, 3,865 theory positions, regenerated by
`python scripts/gen_opening_book.py` and committed, so neither runtime nor CI
touches the network. Theory names a position only once the line is established,
so a ply that matches nothing keeps the deepest name already reached and reports
`in_book: false` — the panel says "out of book", not "unknown".

`win_pct` is an **engine win expectancy**, not a result rate: a logistic on the
Elo equivalent of the evaluation, `1 / (1 + 10^(-cp × ELO_PER_CENTIPOWN / 400))`
with `ELO_PER_CENTIPOWN = 2.0` (one pawn ≈ 200 Elo ⇒ 76%), rounded, clamped to
1..99, and mirrored so `win_pct(-cp) == 100 - win_pct(cp)`
(`app/engine/win_probability.py`). A stored mate distance decides instead: 99 (or 1) within
five moves, 95 (or 5) beyond. The number is emitted from **White's** side —
because the eval graph and the bar both speak White-up — and callers that speak
for one player flip it (`winPctFor` in `apps/web/src/lib/review.ts`). No
third-party population statistics are used anywhere, so nothing depends on an
external host being reachable.

## Achievements (all 🔒, ACH-005..007)

The catalog lives in code (`app/achievements/catalog.py`, 200+ ladder steps
over the stats a player actually generates); the database stores only which
keys a player earned.

| Method & Path | Description |
|---------------|-------------|
| `GET /me/achievements` | `{total, unlocked, items[]}` — every catalog entry with this player's `value`, `unlocked`, `progress` (0..1) and `unlocked_at` |
| `GET /me/achievements/new` | Unlocks not yet celebrated; evaluated lazily, does not mark them seen |
| `POST /me/achievements/seen` | Body `{keys: [...]}` → `200`; acknowledges celebrations so a reload does not replay them |

Unlocks are written on terminal game transitions (`celebrate_at_end`) and after
a completed review; `GET /me/achievements/new` catches anything that only
becomes true mid-game.

## Training (all 🔒, LEARN-001..005)

The Learn section: a curated drill catalog (`app/training/drills.py`, 6 themes ×
3 levels, each re-proved sound by python-chess in `verify.py`) plus puzzles mined
from the caller's own analysed games (`app/training/from_reviews.py`). Every
attempt is appended to `training_attempts`, and the easy→hard ramp, the streak
and the per-theme progress are all recomputed from that log — no mutable counter
to drift.

**The load-bearing rule: a puzzle is served answer-free.** `GET /training/puzzle`
never carries `solution`, `alternatives` or `line` (a test asserts those keys are
absent); the answer only ever leaves the server inside an attempt/reveal verdict,
because the frontend never determines the outcome.

| Method & Path | Description |
|---------------|-------------|
| `GET /training/summary` | Per-theme `{label, solved, attempts, level, pct}` plus `{puzzles_solved, streak, mine_available}` (LEARN-003) |
| `GET /training/puzzle?theme=&source=` | One puzzle at that theme's current level, or the next unsolved mined one (`source=game`); **no answer in the payload**; `404` when nothing is left |
| `GET /training/mine` | The caller's "A move you missed" list — `{key, fen, prompt, game_id, ply}` for each mined puzzle (REV-005) |
| `POST /training/attempts` | Body `{key, uci, reveal?}`. Verdict + reveal `{solved, solution_san, solution_from, solution_to, why, continuation, points_awarded, unlocked_achievements}` |

Errors: `401` everywhere; `404` unknown puzzle key (or a `mine:` key no longer in
the caller's reviews); `422` an illegal or unparseable `uci`. The POST carries the
same-origin CSRF check (`enforce_same_origin`) like the review and online routes.

Points are a **side income**, awarded on a *first* solve only and deduped through
the gameless ledger slot (`slot_key`, partial unique index): `drill` = 2 per
puzzle, `theme_clear` = 5 the first time a theme is cleared (a game move is 1 and
a win is 10, so grinding drills cannot out-earn playing). `reveal: true` ("Show
me") records a no-credit attempt so frustration is never a dead end.

## OpenAPI

- Machine schema: `GET /openapi.json` (validated by `tests/test_openapi.py`).
- Frontend types: `apps/web/src/lib/api-types.ts` (API-022; contract-tested).
