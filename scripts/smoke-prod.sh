#!/usr/bin/env bash
# Production smoke test (REL-013). Exercises the full play loop against a
# deployed API base URL. Fails non-zero on any unexpected status.
# Usage: API_BASE=https://api.example.com ./scripts/smoke-prod.sh
set -euo pipefail

API_BASE="${API_BASE:?set API_BASE, e.g. https://api.example.com}"
JAR="$(mktemp)"
trap 'rm -f "${JAR}"' EXIT

check() { # check <desc> <expected> <actual>
  if [ "$2" != "$3" ]; then
    echo "FAIL: $1 — expected $2, got $3" >&2
    exit 1
  fi
  echo "ok: $1 ($3)"
}

code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/api/v1/health")
check "health" 200 "${code}"

EMAIL="smoke-$(date +%s)@example.com"
code=$(curl -s -o /dev/null -w "%{http_code}" -c "${JAR}" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"s3cret-pass\"}" \
  "${API_BASE}/api/v1/auth/register")
check "register" 201 "${code}"

GID=$(curl -s -b "${JAR}" -H 'Content-Type: application/json' \
  -d '{"mode":"computer"}' "${API_BASE}/api/v1/games" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "ok: create game (id=${GID})"

code=$(curl -s -o /dev/null -w "%{http_code}" -b "${JAR}" \
  -H 'Content-Type: application/json' \
  -d '{"uci":"e2e4","expected_version":1}' \
  "${API_BASE}/api/v1/games/${GID}/moves")
check "submit e2e4" 200 "${code}"

BODY=$(curl -s -b "${JAR}" -H 'Content-Type: application/json' \
  -d '{"expected_version":2,"max_depth":1,"max_time_ms":500}' \
  "${API_BASE}/api/v1/games/${GID}/engine-move")
VER=$(echo "${BODY}" | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])")
check "engine move → version 3" 3 "${VER}"

echo "SMOKE PASS: ${API_BASE}"
