#!/usr/bin/env bash
# Setup step 4 - end-to-end test WITHOUT the AI.
#
# Does exactly what the AI will do, with a tiny deterministic change:
#   status.sh coding -> edit app/index.html -> push.sh -> diag.sh --wait
# Watch the dashboard while it runs. If this is green, the chain works and any
# problem during the demo comes from the AI, not from the platform.
#
# Afterwards: scripts/raz.sh -y
set -euo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

[ -f "$APP_REPO_DIR/app/index.html" ] || die "$APP_REPO_DIR/app/index.html not found (run setup/02 first)"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

log "1/4 status.sh coding"
"$ROOT/scripts/status.sh" coding
sleep 3

log "2/4 Writing a test page in $APP_REPO_DIR/app/index.html"
cat > "$APP_REPO_DIR/app/index.html" <<EOF
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Smoke test</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:sans-serif;
background:#0f1420;color:#e8ecf4}h1{font-size:48px}p{color:#8b97b0}</style></head>
<body><div style="text-align:center"><h1>Smoke test OK</h1>
<p>Deployed by the NKP golden path - ${STAMP}</p></div></body></html>
EOF

log "3/4 push.sh"
"$ROOT/scripts/push.sh" "Smoke test ${STAMP}"

log "4/4 diag.sh --wait (follow it on the dashboard too)"
if "$ROOT/scripts/diag.sh" --wait; then
  ok "Chain validated end to end. Reset with: scripts/raz.sh -y"
else
  code=$?
  warn "Not green (exit $code). The failing step and its reason are printed above."
  warn "Details: scripts/diag.sh  |  then reset with scripts/raz.sh -y"
  exit "$code"
fi
