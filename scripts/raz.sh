#!/usr/bin/env bash
# =============================================================================
# raz.sh — reset the demo to "Demo on hold"
#
#   1. Cancel running GitHub Actions on vibe-demo-app
#      (otherwise a late run could re-commit deploy/ AFTER the reset)
#   2. Reset the local clone to the baseline tag (local page = "Demo on hold")
#   3. Force push the baseline tag to main ([skip ci] commit: no build)
#   4. Ask Flux to resync (best effort)
#   5. Reset the dashboard state file to "idle"
#   6. (--wait) wait until the app serves the "on hold" page again
#
# Usage: ./scripts/raz.sh [--wait] [--yes]
# Requires: git, curl, python3, kubectl
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"

WAIT=false; YES=false
for arg in "$@"; do
  case "$arg" in
    --wait) WAIT=true ;;
    --yes)  YES=true ;;
    *) echo "Unknown option: $arg"; exit 2 ;;
  esac
done

API="https://api.github.com/repos/$GITHUB_OWNER/$APP_REPO"
gh_api() {  # gh_api METHOD PATH
  curl -fsS -X "$1" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$API$2"
}
step() { echo; echo "==> $*"; }
warn() { echo "    WARNING: $*"; }

if ! $YES; then
  read -r -p "Reset the demo ($APP_REPO -> $BASELINE_TAG)? [y/N] " ans
  [[ "$ans" =~ ^[yY]$ ]] || { echo "Cancelled."; exit 0; }
fi

# --- 1. Cancel running runs --------------------------------------------------
step "1/6 Cancel running GitHub Actions"
for status in queued in_progress; do
  ids=$(gh_api GET "/actions/runs?status=$status&per_page=50" \
        | python3 -c 'import sys,json; print(" ".join(str(r["id"]) for r in json.load(sys.stdin)["workflow_runs"]))')
  for id in $ids; do
    echo "    cancelling run $id ($status)"
    gh_api POST "/actions/runs/$id/cancel" >/dev/null || warn "failed to cancel run $id"
  done
done

# --- 2. Local clone -> baseline ---------------------------------------------
step "2/6 Local clone -> tag $BASELINE_TAG"
cd "$APP_REPO_DIR"
AUTH_HEADER="Authorization: Basic $(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
REMOTE_URL="https://github.com/$GITHUB_OWNER/$APP_REPO.git"
git -c http.extraHeader="$AUTH_HEADER" fetch --force --tags "$REMOTE_URL" \
    "refs/tags/$BASELINE_TAG:refs/tags/$BASELINE_TAG"
git checkout -q main 2>/dev/null || git checkout -q -b main
git reset -q --hard "$BASELINE_TAG"
git clean -fdq
BASE_SHA=$(git rev-parse HEAD)
echo "    local main = $BASE_SHA"
git log -1 --format=%B | grep -q '\[skip ci\]' \
  || warn "the $BASELINE_TAG commit message has no [skip ci]: a build will be triggered"

# --- 3. Force push -----------------------------------------------------------
step "3/6 Force push $BASELINE_TAG to main"
git -c http.extraHeader="$AUTH_HEADER" push --force "$REMOTE_URL" HEAD:refs/heads/main

# --- 4. Flux resync (best effort) --------------------------------------------
step "4/6 Request Flux resync"
NOW=$(date +%s)
for kind in gitrepository.source.toolkit.fluxcd.io kustomization.kustomize.toolkit.fluxcd.io; do
  if KUBECONFIG="$WORKLOAD_KUBECONFIG" kubectl annotate "$kind" "$GITOPS_SOURCE_NAME" \
      -n "$PROJECT_NAMESPACE" "reconcile.fluxcd.io/requestedAt=$NOW" --overwrite >/dev/null 2>&1; then
    echo "    $kind/$GITOPS_SOURCE_NAME: resync requested"
  else
    warn "$kind/$GITOPS_SOURCE_NAME not found on the workload cluster (Flux will resync at its interval)"
  fi
done

# --- 5. Dashboard state ------------------------------------------------------
step "5/6 Dashboard -> idle"
mkdir -p "$(dirname "$STATE_FILE")"
python3 - "$STATE_FILE" "$BASE_SHA" <<'PY'
import json, os, sys, datetime
path, sha = sys.argv[1], sys.argv[2]
state = {
    "phase": "idle",
    "sha": None,
    "started_at": None,
    "pushed_at": None,
    "baseline_sha": sha,
    "reset_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(state, f, indent=2)
os.replace(tmp, path)
PY
echo "    $STATE_FILE reset"

# --- 6. Optional wait --------------------------------------------------------
step "6/6 Check the app"
if $WAIT; then
  v=""
  for _ in $(seq 1 60); do
    v=$(curl -fsS --max-time 3 "$APP_URL/version.txt" 2>/dev/null || true)
    if [[ "$v" == "onhold" ]]; then echo "    OK: $APP_URL serves the 'Demo on hold' page"; exit 0; fi
    sleep 3
  done
  warn "after 3 min, $APP_URL does not return 'onhold' (got: '${v:-nothing}')"
  exit 1
else
  echo "    (run with --wait to wait for the 'on hold' page)"
fi

echo; echo "Reset complete."
