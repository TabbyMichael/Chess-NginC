# Phase 12 — Market Readiness Plan

> Ship plan for releasing Chess NginC publicly as SaaS. Four workstreams:
> **12A** observability + abuse defense, **12B** identity + admin floor,
> **12C** fair play (anti-cheat — built, not deferred), plus triggered items
> kept in the debt register. Invariants through all of it: offline-hermetic
> tests, CI gates = done, ownership authorization (404-on-foreign) unchanged,
> SaaS posture keeps the GPL question closed (REL-011/TD-004).

## Stage 12A — Monitoring & Rate Limiting (D14/D15) — ~2–3 days

| ID | Task | Status | Notes |
|----|------|--------|-------|
| MON-001 | JSON-line logs with `request_id` | [x] | logging setup (`app/core/telemetry.py`); middleware assigns one per request; QA-019 stands — no tokens/secrets ever logged |
| MON-002 | `/metrics` via `prometheus-fastapi-instrumentator` | [x] | per-route RED for free; deployment.md §8 rewritten from "to wire" to what exists |
| MON-003 | `engine_analyse_seconds` histogram (label: provider) | [x] | `stockfish` vs `stockfish-cloud` — the label already rides results/reviews |
| MON-004 | `engine_unavailable_total` counter | [x] | the D7 503s; spike = no binary AND no key |
| MON-005 | `rate_limit_rejections_total{bucket}` | [x] | auth/moves/assistant/review/training — cheapest brute-force alarm |
| MON-006 | `cloud_units_estimate_daily` counter + upstream 4xx counter | [x] | the shared 2,000-unit pot; dormant while local-first wins |
| MON-007 | `ws_connections_active` gauge | [x] | visibility into the single-replica socket island (TD-012) |
| MON-008 | Alert-target doc pass | [x] | `/ready` failing, sustained 5xx, engine 503 spike, cloud budget, backup failure — deployment.md §8 |
| RL-001 | Review limiter: 10/hour/user, `force` costs 2 | [x] | the ~12 s held-engine surface is unlimited today (TD-013) |
| RL-002 | Training attempts limiter: 60/min/user | [x] | writes ledger rows; needs a ceiling |
| RL-003 | Global cloud-budget guard: stop ~1,800 units/day → clean 503 | [x] | app-wide counter in the cloud provider; trip BEFORE upstream |
| RL-004 | `Retry-After` on every 429 | [x] | all buckets |
| RL-005 | Redis limiter swap | [ ] | **trigger: TD-012** (2nd replica / multi-worker) — same `check_*` signatures |

## Stage 12B — Identity & Admin Floor (D16 + TD-005) — ~3–4 days

| ID | Task | Status | Notes |
|----|------|--------|-------|
| SEC-021 | Email verification on registration | [ ] | TD-005; token flow on the SMTP seam; `users.email_verified_at`; unverified can play, cannot claim points/rank |
| SEC-022 | Real reset email (replaces log-printing) | [ ] | dev keeps log mode via empty `smtp_host` |
| SEC-023 | `users.role`: player/moderator/admin, CHECK, default player | [ ] | ONE column — roles/permissions join table banned until a 4th role is real |
| SEC-024 | `require_role()` dependency beside `get_current_user` | [ ] | `deps.py`; privileged routes = one annotation |
| SEC-025 | `audit_log` table | [ ] | same migration batch as SEC-023; an admin write without an audit row is a bug |
| SEC-026 | Support endpoints (audited): reset-password, points adjustment as reason-only ledger row, game note | [ ] | never mutate `users.points` directly — rides `PointAward` |
| SEC-027 | Session revocation on role change / support reset | [ ] | opaque DB tokens already give the kill switch; keep the property |
| SEC-028 | `users.status` (active/suspended/banned) enforced at login + WS + lobby | [ ] | enforcement point for 12C verdicts |

## Stage 12C — Fair Play / Anti-Cheat (D17) — C1 1 day · C2 3–5 days · C3 2–3 days

**Design principles (ADR D17):**
- **Evidence over auto-action.** Detection never bans and never revokes — it
  flags. A moderator (12B) judges from the evidence page. A false positive that
  locks out a real player costs more than a cheat that slips through a week.
- **Hashes, not logs.** IP stored salted-hashed (SHA-256) with a 180-day
  retention TTL, disclosed in the ToS. No device fingerprinting beyond UA.
- **Reuse the seams.** Engine correlation runs through the provider seam (D7)
  on a warm batch (ANL-003) at bounded depth — no new engine path.
- **Server-measured timing only.** Client-reported clock is a gift to cheaters.

### C1 — Capture (ships BEFORE launch; detection without history is blind)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| FP-001 | `game_moves.think_ms` (server-measured between plies) + `game_moves.ip_hash` | [ ] | migration; computed by games service on record |
| FP-002 | `auth_events` table (kind, ip_hash, user_id nullable, outcome, created_at) | [ ] | login/register/reset attempts; doubles as brute-force + cluster signal |
| FP-003 | Salt + retention (`fairplay_ip_salt`, 180-day pruning script) | [ ] | scripts/ + test that old rows are eligible |

### C2 — Detection (`app/fairplay/`)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| FP-010 | Agreement-rate signal: bounded Stockfish sweep of critical positions, % matching top-1/top-3 | [ ] | `open_stockfish_provider(for_review=True)`; sample N plies, never the whole game at 25 |
| FP-011 | Move-time profile: flat ultra-fast across complex positions; clock-gambler pattern | [ ] | pure stats |
| FP-012 | Clustering: shared `ip_hash` between paired accounts; registration bursts | [ ] | SQL + fixtures |
| FP-013 | Weighted score → threshold → `fairplay_flags` row (game, user, signals JSON, score, status) | [ ] | conservative thresholds (TD-022); store raw signals so thresholds can change without recompute |
| FP-014 | Trigger on online-game completion, never slowing the terminal response | [ ] | job seam (ANL-008) if landed, else bounded post-terminal task |
| FP-015 | Hermetic tests: scripted `AnalysisResult` via fake provider; fixture signals | [ ] | CI never needs a binary or key |

### C3 — Moderation & Enforcement (needs 12B)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| FP-020 | `GET /admin/fairplay/flags` queue (filter status/score) | [ ] | `require_role("moderator", "admin")` |
| FP-021 | Flag evidence page: flagged plies vs engine top-3, time chart, cluster links | [ ] | evidence presentation is the product |
| FP-022 | Verdict endpoint: not_guilty / guilty + penalty {warn, points_revoke, game_void, suspend_temp, ban_perm} | [ ] | every verdict audited; game_void = result override, moves stay |
| FP-023 | Player appeal `POST /games/{id}/appeal` → admin queue | [ ] | trust infrastructure, cheap |
| FP-024 | Status enforcement: banned can't login/queue/play | [ ] | SEC-028 check in auth + lobby + WS handshake |

## Triggered / adjacent (decided, kept honest)
- **TD-013 → ANL-008** review job queue: the other launch blocker; MON-003/004
  measure the real saturation point. Sequence: 12A+12B+FP-C1 → soft launch →
  ANL-008 → FP-C2 calibration.
- **TD-012 → Redis** (limiters, lobby, pub/sub) at the second-replica trigger.
- Deferred with seams kept: Sentry/OTel (`main.py`), semantic recall (D13),
  signup CAPTCHA, rating-trajectory detection (later FP signal).

## New debt this plan creates (recorded, not hidden — TD-020 was already taken by FTS recall)
- **TD-021**: per-IP limits meaningless behind a proxy until `X-Forwarded-For`
  trust is configured — decide at 12B deploy, only trust our proxy.
- **TD-022**: fairplay thresholds uncalibrated until real flag volume exists.
- **TD-023**: detection runs on completed games only; in-game live detection deferred.

## Build order (dependencies, not dates)
12A → 12B (SEC-023..028 first; SEC-021/022 alongside) → **FP-C1 before launch** →
soft launch → FP-C2 (calibrate on real games incl. own) → FP-C3 → ANL-008.

## Definition of done (every stage)
CI green in workflow order (ruff check/format, mypy, alembic upgrade+check on a
fresh DB, pytest; eslint, tsc, vitest, build, prettier) + live compose smoke for
the new surface + IMPLEMENTATION_LOG entry + checklist/debt rows updated here and
in `PROJECT_CHECKLIST.md`.
