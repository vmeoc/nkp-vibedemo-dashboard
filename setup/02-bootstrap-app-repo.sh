#!/usr/bin/env bash
# Setup step 2 - create the local vibe-demo-app repo from app-template/,
# commit the "Demo on hold" baseline, tag it `baseline`, push it to GitHub,
# then build the :onhold image once.
#
# Before running:
#   * create an EMPTY public repo on github.com: <GITHUB_OWNER>/<APP_REPO>
#     (no README, no licence)
#   * this platform repo must be on GitHub too (PLATFORM_REPO) and either
#     public, or with Settings > Actions > General > Access allowing your repos:
#     the app repo calls its reusable workflow.
#   * fill GITHUB_TOKEN, GITHUB_OWNER in .env
set -euo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

[ -n "${GITHUB_TOKEN:-}" ] || die "GITHUB_TOKEN is empty in .env"
[ -n "${GITHUB_OWNER:-}" ] || die "GITHUB_OWNER is empty in .env"
PLATFORM_REPO="${PLATFORM_REPO:-$GITHUB_OWNER/nkp-vibe-demo-dashboard}"
OWNER_LC="$(printf '%s' "$GITHUB_OWNER" | tr '[:upper:]' '[:lower:]')"
REPO_LC="$(printf '%s' "$APP_REPO" | tr '[:upper:]' '[:lower:]')"
IMAGE="ghcr.io/$OWNER_LC/$REPO_LC"

if [ -e "$APP_REPO_DIR" ] && [ -n "$(ls -A "$APP_REPO_DIR" 2>/dev/null)" ]; then
  die "$APP_REPO_DIR already exists and is not empty. Remove it or change APP_REPO_DIR."
fi

log "Creating $APP_REPO_DIR from app-template/"
"$PY" -m vibedemo.cli template --src "$ROOT/app-template" --dst "$APP_REPO_DIR" \
  --set "PLATFORM_REPO=$PLATFORM_REPO" --set "NAMESPACE=$NAMESPACE" \
  --set "PLATFORM_DIR_NAME=$(basename "$ROOT")"

log "Rendering the baseline deploy/ (image $IMAGE:onhold)"
"$PY" -m vibedemo.cli render --contract "$APP_REPO_DIR/contract.yaml" \
  --image "$IMAGE:onhold" --sha onhold --namespace "$NAMESPACE" --out "$APP_REPO_DIR/deploy"

log "Creating the git repository"
AUTH_HEADER="$("$PY" -c 'import os; from vibedemo.sources import git_auth_header; print(git_auth_header(os.environ["GITHUB_TOKEN"]))')"
g() { git -C "$APP_REPO_DIR" "$@"; }
g init --quiet
g checkout --quiet -B main
g add -A
g -c user.name="${GIT_AUTHOR_NAME:-vibe-demo}" -c user.email="${GIT_AUTHOR_EMAIL:-vibe-demo@users.noreply.github.com}" \
  commit --quiet -m "baseline: demo on hold [skip ci]"
g tag -f baseline >/dev/null
g remote add origin "https://github.com/$GITHUB_OWNER/$APP_REPO.git"

log "Pushing main and the baseline tag to github.com/$GITHUB_OWNER/$APP_REPO"
g -c "http.https://github.com/.extraheader=$AUTH_HEADER" push --quiet --force -u origin main
g -c "http.https://github.com/.extraheader=$AUTH_HEADER" push --quiet --force origin refs/tags/baseline
ok "Baseline pushed"

log "Building the :onhold image (workflow onhold.yml)"
sleep 5   # let GitHub register the workflows of the first push
"$PY" -m vibedemo.cli dispatch onhold.yml || warn "start it by hand: GitHub > $APP_REPO > Actions > 'Build on-hold image' > Run workflow"

cat <<EOF

$(ok "Done.")
Manual steps left (once):
  1. When the 'Build on-hold image' workflow is green, make the package PUBLIC:
     github.com/$GITHUB_OWNER?tab=packages > $REPO_LC > Package settings > Change visibility > Public
  2. NKP UI > Project '${PROJECT_NAME:-vibe-demo}' > Continuous Deployment (CD) > Add GitOps Source:
       ID (name)       : $GITOPS_SOURCE
       Repository URL  : https://github.com/$GITHUB_OWNER/$APP_REPO
       Git Ref Type    : Branch -> main
       Path            : ./deploy
  3. Check it: setup/03-check-gitops-source.sh
EOF
