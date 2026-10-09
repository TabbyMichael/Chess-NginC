# Contributing

Thanks for contributing. This project is built incrementally and verified at every step — read this before making changes.

## Before you start

1. Read `docs/development-loops.md` (the mandatory LOOP A–H machine) and `docs/code-standards.md`.
2. Check `PROJECT_CHECKLIST.md` for the current state and pick a task whose dependencies are satisfied.
3. Run `git status` and confirm the working tree is clean.

## Commit & PR standards

Use conventional commit prefixes:

- `feat:` — new functionality
- `fix:` — bug fixes
- `test:` — tests
- `refactor:` — restructuring without behavior change
- `docs:` — documentation
- `chore:` — tooling and maintenance

Examples:

```
feat(engine): implement alpha-beta pruning
fix(game): reject illegal castling moves
test(engine): cover terminal position evaluation
refactor(api): separate game service from routes
```

Every pull request must explain:
- the change and why,
- tests performed (exact commands + results),
- any migration or security implications,
- known technical debt introduced or addressed.

## Quality gates (run before merge)

| Area | Command (once toolchain is configured) |
|------|----------------------------------------|
| Python lint/format | `ruff format --check . && ruff check .` |
| Python type check | `mypy app` (or configured equivalent) |
| Python tests | `pytest` |
| Frontend lint | `npm run lint` |
| Frontend type check | `npx tsc --noEmit` |
| Frontend tests | `npm run test -- --run` |
| Production build | `npm run build` |
| Migration validation | `alembic upgrade head` (dedicated test DB only) |

A failed required gate prevents a PR from being ready to merge.

## Review checklist

- Single responsibility and clear module boundaries (no search in API, no DB in engine).
- Explicit types and validated inputs.
- Expected errors handled without hiding failures.
- Tests for normal behavior and important edge cases.
- No secrets, dead code, debug prints, or undocumented placeholders.
- No unnecessary dependencies or duplicated logic.

## Definition of clean code

Follows naming/formatting; explicit types + validated inputs; business logic separated from UI/API/persistence; expected errors handled; tests included; quality gates pass; no unnecessary deps or duplication; deliberate shortcuts documented with a repayment trigger.
