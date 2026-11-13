#!/usr/bin/env bash
# Setup step 0 - check tools and .env before anything else.
set -uo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

fail=0
need() { if command -v "$1" >/dev/null 2>&1; then ok "$1 found"; else warn "$1 missing - $2"; fail=1; fi; }
need python3 "Python 3.9+ is required"
need git "install git"
need kubectl "needed for MODE=live and setup"
need curl "needed by raz.sh and setup"
need opencode "the AI coding agent"

"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  && ok "python $("$PY" -c 'import platform; print(platform.python_version())')" \
  || { warn "python 3.9+ required"; fail=1; }

[ -f "$ROOT/.env" ] && ok ".env present" || { warn ".env missing: cp .env.example .env"; fail=1; }
for var in GITHUB_TOKEN GITHUB_OWNER; do
  [ -n "${!var:-}" ] && ok "$var set" || { warn "$var empty in .env"; fail=1; }
done
echo "MODE=$MODE  NAMESPACE=$NAMESPACE  APP_REPO_DIR=$APP_REPO_DIR"

if [ "$MODE" = "live" ]; then
  kc get namespace "$NAMESPACE" >/dev/null 2>&1 && ok "namespace $NAMESPACE reachable" \
    || warn "namespace $NAMESPACE not reachable (normal before setup/01)"
fi
exit $fail
