#!/usr/bin/env bash
# Start the Pipeline Monitor web page (default http://127.0.0.1:8090).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
exec "$PY" "$ROOT/dashboard/server.py"
