"""Verify the drill catalog outside the test runner.

Run from ``apps/api`` with the project venv (it needs ``chess``):

    python scripts/check_drills.py

It exists so a contributor can re-prove every position while authoring, without
waiting for pytest. The same ``verify_all`` is asserted in the test suite, so the
build already fails on an unsound drill either way — this is the fast loop.
Exit code 1 lists the offending drills and their problems.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.training.drills import DRILLS  # noqa: E402
from app.training.verify import verify_all  # noqa: E402


def main() -> int:
    problems = verify_all(DRILLS)
    if problems:
        print(f"{len(problems)} drill problem(s) across {len(DRILLS)} drills:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"All {len(DRILLS)} drills are sound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
