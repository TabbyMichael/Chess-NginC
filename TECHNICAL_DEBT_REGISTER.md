# Technical Debt Register

> Known debt, reasons, impact, affected modules, remediation plan, repayment trigger, status.
> Debt is honest and expected; never claim it is zero.

| ID | Description | Reason | Impact / Severity | Modules | Remediation | Repayment trigger | Status |
|----|-------------|--------|-------------------|---------|-------------|-------------------|--------|
| TD-001 | Pure-Python search will be slow at depth | Iterate quickly; python-chess for rules | Medium — limits search depth/strength | `engine/custom` | Profile; consider compiled core (C/Rust/extension) | Move latency exceeds target | Open |
| TD-002 | Docker installed (29.8.2); compose verified end-to-end | Local env now has Docker | Low — resolved | infra | Full `docker compose up` verified (db/api/web); no further infra work | n/a | Resolved |
| TD-003 | pnpm not installed; npm chosen | Tool availability | Low — package manager divergence from spec | web | Standardize once, then lockfile | Team/CI requires pnpm | Open |
| TD-004 | Stockfish licensing reviewed; binary not bundled | GPL-3.0 would infect the service if distributed | Medium — resolved for this repo | engine/stockfish | Documented apt/upstream install at deploy (REL-011); SBOM only if ever distributing the binary | If Stockfish is ever bundled | Resolved |
| TD-005 | Email verification & password reset deferred | Not needed for local dev | High for public release | identity | SEC-018/019 implementation | Before public registration | Deferred |
| TD-006 | Full PGN stored/derived from moves (no cached copy) | Avoid competing representations | Low | game/history | Generate PGN from moves; add cache only if needed | Measured performance/recovery need | Accepted |
| TD-007 | Single engine worker initially | Keep concurrency bounded | Medium under load | engine | Bounded worker pool | Concurrent demand requires it | Accepted |
| TD-008 | Disk at 99% capacity on dev machine | External environment | High — blocks builds/installs | infra/ops | Free space (user action) | Before installing dependencies | Open |
| TD-009 | npm cannot write its cache/logs under `$HOME` | Assistant file sandbox (workspace-write) blocks writes outside the workspace; npm misreports as "root-owned files" | Low — `--cache $(mktemp -d)` workaround proven; all deps already installed | web | Use temp `--cache` for future `npm install`; **no `sudo chown` needed** (ownership already correct) | Next `npm install` | Open |
| TD-010 | `uvicorn[standard]` (uvloop/httptools) not yet used | 3.14 wheel availability unconfirmed | Low — fewer prod niceties | api | Confirm wheels, then enable extras | Before production | Open |
| TD-011 | Starlette `TestClient` deprecates `httpx` in favor of `httpx2` | Upstream forward-migration | Low — test warning only today | api/tests | Migrate to httpx2 when stable | When starlette drops httpx | Open |

## Watched risks (from spec)

Python search performance · duplicate chess rules · inconsistent game state · duplicated API contracts · missing transaction boundaries · excessive engine concurrency · unbounded resource usage · poor special-move test coverage · authentication shortcuts · unreviewed licensing · premature microservices · overengineered abstractions · missing recovery/ops procedures.
