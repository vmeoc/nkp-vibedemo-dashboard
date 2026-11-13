#!/usr/bin/env bash
# RAZ - reset the demo to "Demo on hold".
#
#   1. vibe-demo-app: main is force-reset to the `baseline` tag and pushed
#      (the baseline commit message contains [skip ci]: no build is triggered;
#       its deploy/ points to the prebuilt :onhold image)
#   2. Flux is asked to reconcile now (annotation, no flux CLI needed)
#   3. the dashboard state is emptied (all steps back to "pending")
#   4. waits until the LoadBalancer serves the on-hold page again
#   5. removes apps created during the demo under another name (if Flux prune is off)
#
# The platform repo (this one) is never touched.
#
#   raz.sh        asks for confirmation
#   raz.sh -y     no confirmation (use during the demo)
set -euo pipefail
. "$(dirname "$0")/_common.sh"

YES=0
[ "${1:-}" = "-y" ] && YES=1
RAZ_WAIT="${RAZ_WAIT:-90}"   # stays under agent tool timeouts

if [ "$MODE" = "simulated" ]; then
  "$PY" -m vibedemo.cli status idle >/dev/null
  ok "MODE=simulated: dashboard state reset, nothing else touched."
  exit 0
fi

[ -d "$APP_REPO_DIR/.git" ] || die "$APP_REPO_DIR is not a git repo (run setup/02-bootstrap-app-repo.sh)"
[ -n "${GITHUB_TOKEN:-}" ] || die "GITHUB_TOKEN is empty in .env"

if [ "$YES" -ne 1 ]; then
  printf 'This will force-push the baseline to %s/%s (main) and discard local changes in %s.\nContinue? [y/N] ' \
    "${GITHUB_OWNER:-?}" "$APP_REPO" "$APP_REPO_DIR"
  read -r answer
  case "$answer" in y|Y|yes|YES) ;; *) echo "Cancelled."; exit 0 ;; esac
fi

AUTH_HEADER="$("$PY" -c 'import os,sys; from vibedemo.sources import git_auth_header; print(git_auth_header(os.environ["GITHUB_TOKEN"]))')"
git_auth() { git -C "$APP_REPO_DIR" -c "http.https://github.com/.extraheader=$AUTH_HEADER" "$@"; }

# 1. Git ---------------------------------------------------------------------
log "Resetting $APP_REPO to the baseline tag"
git_auth fetch --quiet --force origin "refs/tags/baseline:refs/tags/baseline" \
  || warn "could not fetch the baseline tag from GitHub, using the local one"
git -C "$APP_REPO_DIR" rev-parse --verify --quiet "refs/tags/baseline" >/dev/null \
  || die "tag 'baseline' not found (run setup/02-bootstrap-app-repo.sh)"
git -C "$APP_REPO_DIR" reset --quiet --hard
git -C "$APP_REPO_DIR" clean --quiet -fd
git -C "$APP_REPO_DIR" checkout --quiet -B main baseline
git_auth push --quiet --force origin main
ok "main = baseline ($(git -C "$APP_REPO_DIR" rev-parse --short HEAD)) pushed"

BASELINE_APP="$(sed -n 's/^app:[[:space:]]*\([a-z0-9-]*\).*/\1/p' "$APP_REPO_DIR/contract.yaml" | head -n1)"
[ -n "$BASELINE_APP" ] || die "cannot read 'app:' from the baseline contract.yaml"

# 2. Flux --------------------------------------------------------------------
log "Asking Flux to reconcile now"
NOW="$(date +%s)"
kc -n "$NAMESPACE" annotate --overwrite "gitrepository.source.toolkit.fluxcd.io/$GITOPS_SOURCE" \
  "reconcile.fluxcd.io/requestedAt=$NOW" >/dev/null \
  && ok "GitRepository $GITOPS_SOURCE" || warn "GitRepository $GITOPS_SOURCE not found in $NAMESPACE (check GITOPS_SOURCE)"
kc -n "$NAMESPACE" annotate --overwrite "kustomization.kustomize.toolkit.fluxcd.io/$GITOPS_SOURCE" \
  "reconcile.fluxcd.io/requestedAt=$NOW" >/dev/null \
  && ok "Kustomization $GITOPS_SOURCE" || warn "Kustomization $GITOPS_SOURCE not found in $NAMESPACE"

# 3. Dashboard state -----------------------------------------------------------
"$PY" -m vibedemo.cli status idle >/dev/null
ok "Dashboard reset (all steps pending)"

# 4. Wait for the on-hold page --------------------------------------------------
log "Waiting for '$BASELINE_APP' to serve the on-hold page (max ${RAZ_WAIT}s)"
deadline=$(( $(date +%s) + RAZ_WAIT ))
served=""
ip=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  ip="$(kc -n "$NAMESPACE" get svc "$BASELINE_APP" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  if [ -n "$ip" ]; then
    served="$(curl -fsS --max-time 3 "http://$ip/version.txt" 2>/dev/null | tr -d '[:space:]' || true)"
    [ "$served" = "onhold" ] && break
  fi
  sleep 3
done
if [ "$served" = "onhold" ]; then
  ok "Demo on hold at http://$ip/"
else
  warn "on-hold page not confirmed yet (served: '${served:-nothing}'). Check: scripts/diag.sh, kubectl -n $NAMESPACE get kustomization,deploy,svc"
fi

# 5. Leftovers -------------------------------------------------------------------
for name in $(kc -n "$NAMESPACE" get deploy -l vibedemo.nutanix.com/managed=true \
                -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null); do
  if [ "$name" != "$BASELINE_APP" ]; then
    log "Removing leftover app '$name' (created during the demo)"
    kc -n "$NAMESPACE" delete deploy "$name" --ignore-not-found >/dev/null
    kc -n "$NAMESPACE" delete svc "$name" --ignore-not-found >/dev/null
  fi
done

ok "RAZ done."
