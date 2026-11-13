#!/usr/bin/env bash
# Setup step 5 - push the latest agent files of app-template/ (AGENTS.md,
# CONTRACT.md, opencode.json) into vibe-demo-app and move the `baseline` tag,
# so that every RAZ restores the new instructions.
#
# Re-run it whenever these template files change. It ends like a RAZ:
# main = new baseline, dashboard idle. Workflows are not touched (no Workflows
# permission needed on the token).
set -euo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

FILES="AGENTS.md CONTRACT.md opencode.json"

[ -d "$APP_REPO_DIR/.git" ] || die "$APP_REPO_DIR is not a git repo (run setup/02-bootstrap-app-repo.sh first)"
[ -n "${GITHUB_TOKEN:-}" ] || die "GITHUB_TOKEN is empty in .env"
PLATFORM_REPO="${PLATFORM_REPO:-$GITHUB_OWNER/nkp-vibe-demo-dashboard}"

AUTH_HEADER="$("$PY" -c 'import os; from vibedemo.sources import git_auth_header; print(git_auth_header(os.environ["GITHUB_TOKEN"]))')"
g() { git -C "$APP_REPO_DIR" "$@"; }
ga() { git -C "$APP_REPO_DIR" -c "http.https://github.com/.extraheader=$AUTH_HEADER" "$@"; }

log "Starting from the current baseline"
ga fetch --quiet --force origin "refs/tags/baseline:refs/tags/baseline" || warn "using the local baseline tag"
g reset --quiet --hard
g clean --quiet -fd
g checkout --quiet -B main baseline

log "Rendering the agent files from app-template/"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
"$PY" -m vibedemo.cli template --src "$ROOT/app-template" --dst "$TMP/app" \
  --set "PLATFORM_REPO=$PLATFORM_REPO" --set "NAMESPACE=$NAMESPACE" >/dev/null
for f in $FILES; do
  cp "$TMP/app/$f" "$APP_REPO_DIR/$f"
done

g add $FILES
if g diff --cached --quiet; then
  ok "Agent files already up to date - nothing to do"
  exit 0
fi
g diff --cached --stat
g -c user.name="${GIT_AUTHOR_NAME:-vibe-demo}" -c user.email="${GIT_AUTHOR_EMAIL:-vibe-demo@users.noreply.github.com}" \
  commit --quiet -m "baseline: refresh agent files [skip ci]"
g tag -f baseline >/dev/null

log "Pushing the new baseline"
ga push --quiet --force origin main
ga push --quiet --force origin refs/tags/baseline
"$PY" -m vibedemo.cli status idle >/dev/null
ok "baseline = $(g rev-parse --short HEAD) - next RAZ will restore these files"
