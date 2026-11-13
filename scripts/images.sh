#!/usr/bin/env bash
# Download free images from Wikimedia Commons into <APP_REPO_DIR>/app/images/.
#   images.sh "Eiffel tower" [--count 3]
# Prints the <img> tags to use and the credits line for the footer.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
[ $# -ge 1 ] || die 'usage: vibe images "<subject in English>" [--count N]'
exec "$PY" -m vibedemo.cli images "$@"
