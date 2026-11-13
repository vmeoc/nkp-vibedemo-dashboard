#!/usr/bin/env bash
# Setup step 3 (after the GitOps Source is created in the NKP UI) - check that
# Flux objects exist in the project namespace and that the on-hold page is served.
# Prints the values to keep in .env if names differ.
set -euo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

log "Flux objects in namespace $NAMESPACE"
kc -n "$NAMESPACE" get gitrepositories.source.toolkit.fluxcd.io,kustomizations.kustomize.toolkit.fluxcd.io \
  || die "cannot list Flux objects (KUBECONFIG must point to the workload cluster)"

if ! kc -n "$NAMESPACE" get "kustomizations.kustomize.toolkit.fluxcd.io/$GITOPS_SOURCE" >/dev/null 2>&1; then
  warn "No Kustomization named '$GITOPS_SOURCE'. Set GITOPS_SOURCE in .env to the NAME shown above."
  exit 1
fi
ok "Kustomization $GITOPS_SOURCE found"

echo
echo "GitRepository interval : $(kc -n "$NAMESPACE" get "gitrepositories.source.toolkit.fluxcd.io/$GITOPS_SOURCE" -o jsonpath='{.spec.interval}' 2>/dev/null || echo '?')"
echo "Kustomization interval : $(kc -n "$NAMESPACE" get "kustomizations.kustomize.toolkit.fluxcd.io/$GITOPS_SOURCE" -o jsonpath='{.spec.interval}')"
echo "Kustomization prune    : $(kc -n "$NAMESPACE" get "kustomizations.kustomize.toolkit.fluxcd.io/$GITOPS_SOURCE" -o jsonpath='{.spec.prune}')"
echo "Kustomization path     : $(kc -n "$NAMESPACE" get "kustomizations.kustomize.toolkit.fluxcd.io/$GITOPS_SOURCE" -o jsonpath='{.spec.path}')"
echo "Ready                  : $(kc -n "$NAMESPACE" get "kustomizations.kustomize.toolkit.fluxcd.io/$GITOPS_SOURCE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status} {.status.conditions[?(@.type=="Ready")].message}')"
echo

log "Demo app objects"
kc -n "$NAMESPACE" get deploy,svc -l vibedemo.nutanix.com/managed=true -o wide || true

ip="$(kc -n "$NAMESPACE" get svc -l vibedemo.nutanix.com/managed=true \
      -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}{.items[0].status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
if [ -n "$ip" ]; then
  served="$(curl -fsS --max-time 3 "http://$ip/version.txt" 2>/dev/null | tr -d '[:space:]' || true)"
  if [ "$served" = "onhold" ]; then ok "On-hold page served at http://$ip/"; else warn "http://$ip/version.txt returned '${served:-nothing}' (expected 'onhold')"; fi
else
  warn "No LoadBalancer IP yet"
fi
