#!/usr/bin/env bash
# Check contract.yaml against the platform rules and print it in plain English.
#   validate.sh                 -> checks <APP_REPO_DIR>/contract.yaml
#   validate.sh path/to/file    -> checks another file
# Exit code 0 = accepted, 3 = refused (the reasons are printed).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
exec "$PY" -m vibedemo.cli validate "$@"
