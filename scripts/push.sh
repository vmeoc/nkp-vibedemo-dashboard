#!/usr/bin/env bash
# Validate the contract, commit everything in the app repo and push to GitHub.
# Records the commit SHA for the dashboard.
#   push.sh "Add a contact form"
# In MODE=simulated nothing is sent to GitHub (a fake SHA is recorded).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
[ $# -ge 1 ] || die 'usage: push.sh "<commit message>"'
exec "$PY" -m vibedemo.cli push "$*"
