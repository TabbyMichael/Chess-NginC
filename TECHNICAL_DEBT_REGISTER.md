# Technical Debt Register

> Known debt, reasons, impact, affected modules, remediation plan, repayment trigger, status.
> Debt is honest and expected; never claim it is zero.

| ID | Description | Reason | Impact / Severity | Modules | Remediation | Repayment trigger | Status |
|----|-------------|--------|-------------------|---------|-------------|-------------------|--------|
| TD-001 | Pure-Python search will be slow at depth | Iterate quickly; python-chess for rules | Medium — limits search depth/strength | `engine/custom` | Profile; consider compiled core (C/Rust/extension) | Move latency exceeds target | Open |
| TD-002 | Docker not installed locally | Local environment lacks Docker | Low — blocks FND-018/019 verification | infra | Install Docker or document local-Postgres path | Before CI/Compose work | Open |
| TD-003 | pnpm not installed; npm chosen | Tool availability | Low — package manager divergence from spec | web | Standardize once, then lockfile | Team/CI requires pnpm | Open |
| TD-004 | Stockfish licensing not yet reviewed | Binary not yet distributed | Medium — GPL-3.0 obligations | engine/stockfish | BEN-003 review + SBOM | Before distributing Stockfish | Open |
| TD-005 | Email verification & password reset deferred | Not needed for local dev | High for public release | identity | SEC-018/019 implementation | Before public registration | Deferred |
| TD-006 | Full PGN stored/derived from moves (no cached copy) | Avoid competing representations | Low | game/history | Generate PGN from moves; add cache only if needed | Measured performance/recovery need | Accepted |
| TD-007 | Single engine worker initially | Keep concurrency bounded | Medium under load | engine | Bounded worker pool | Concurrent demand requires it | Accepted |
| TD-008 | Disk at 99% capacity on dev machine | External environment | High — blocks builds/installs | infra/ops | Free space (user action) | Before installing dependencies | Open |

## Watched risks (from spec)

Python search performance · duplicate chess rules · inconsistent game state · duplicated API contracts · missing transaction boundaries · excessive engine concurrency · unbounded resource usage · poor special-move test coverage · authentication shortcuts · unreviewed licensing · premature microservices · overengineered abstractions · missing recovery/ops procedures.
