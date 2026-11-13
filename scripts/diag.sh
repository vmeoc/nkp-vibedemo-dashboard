#!/usr/bin/env bash
# Show the six pipeline steps - exactly what the dashboard shows.
#   diag.sh            one-shot table
#   diag.sh --wait     print each change until the app is live (exit 0),
#                      a step failed (exit 1) or timeout (exit 2)  <- used by the AI
#   diag.sh --watch    refresh the table every 3s (Ctrl-C to stop)
#   diag.sh --json     raw JSON (same as GET /api/status)
set -euo pipefail
. "$(dirname "$0")/_common.sh"
exec "$PY" -m vibedemo.cli diag "$@"
