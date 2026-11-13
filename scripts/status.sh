#!/usr/bin/env bash
# Tell the dashboard what the AI is doing.
#   status.sh coding   -> "Code under development" turns blue (call it BEFORE writing code)
#   status.sh show     -> print the current state
#   status.sh idle     -> back to "waiting" (raz.sh does this for you)
set -euo pipefail
. "$(dirname "$0")/_common.sh"
exec "$PY" -m vibedemo.cli status "${1:-show}"
