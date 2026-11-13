#!/usr/bin/env bash
# =============================================================================
# One-time setup: create the NKP project "vibe-demo" with a FIXED namespace
# (no random suffix).
#
# Usage: ./setup/01-create-project.sh     (server-side dry-run, then creation)
#
# Requires: kubectl, a filled-in .env (MGMT_KUBECONFIG, WORKLOAD_KUBECONFIG,
#           WORKSPACE_NAME, CLUSTER_NAME, PROJECT_NAMESPACE).
# Afterwards: create the GitOps Source in the NKP UI (see end of script).
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"

export KUBECONFIG="$MGMT_KUBECONFIG"
LABEL_KEY="vibe-demo"

echo "==> 1/5 Namespace of workspace '$WORKSPACE_NAME'"
WS_NS=$(kubectl get workspaces.workspaces.kommander.mesosphere.io "$WORKSPACE_NAME" \
          -o jsonpath='{.status.namespaceRef.name}')
if [[ -z "$WS_NS" ]]; then
  echo "ERROR: workspace '$WORKSPACE_NAME' not found. Existing workspaces:"
  kubectl get workspaces.workspaces.kommander.mesosphere.io \
    -o custom-columns=NAME:.metadata.name,NAMESPACE:.status.namespaceRef.name
  exit 1
fi
echo "    -> $WS_NS"

echo "==> 2/5 Label cluster '$CLUSTER_NAME' (used for project placement)"
kubectl get kommanderclusters -n "$WS_NS" "$CLUSTER_NAME" >/dev/null || {
  echo "ERROR: cluster '$CLUSTER_NAME' not found in $WS_NS. Existing clusters:"
  kubectl get kommanderclusters -n "$WS_NS"
  exit 1
}
kubectl label kommanderclusters -n "$WS_NS" "$CLUSTER_NAME" "$LABEL_KEY=true" --overwrite

read -r -d '' PROJECT_YAML <<EOF || true
apiVersion: workspaces.kommander.mesosphere.io/v1alpha1
kind: Project
metadata:
  name: ${PROJECT_NAMESPACE}
  namespace: ${WS_NS}
spec:
  workspaceRef:
    name: ${WORKSPACE_NAME}
  # FIXED namespace name. Immutable: to change it, delete and recreate the project.
  namespaceName: ${PROJECT_NAMESPACE}
  placement:
    clusterSelector:
      matchLabels:
        ${LABEL_KEY}: "true"
EOF

echo "==> 3/5 API validation (server-side dry-run, nothing is created)"
echo "$PROJECT_YAML" | kubectl apply --dry-run=server -f -

echo "==> 4/5 Create project"
echo "$PROJECT_YAML" | kubectl apply -f -

echo "==> 5/5 Verify"
NS=""
for _ in $(seq 1 30); do
  NS=$(kubectl get projects.workspaces.kommander.mesosphere.io -n "$WS_NS" "$PROJECT_NAMESPACE" \
         -o jsonpath='{.status.namespaceRef.name}' 2>/dev/null || true)
  [[ -n "$NS" ]] && break
  sleep 2
done
echo "    Project namespace (management cluster): ${NS:-<not ready yet>}"
echo "    On the workload cluster:"
KUBECONFIG="$WORKLOAD_KUBECONFIG" kubectl get namespace "$PROJECT_NAMESPACE" \
  || echo "    (not propagated yet, retry: kubectl get ns $PROJECT_NAMESPACE)"

cat <<EOF

Next step (NKP UI): project '$PROJECT_NAMESPACE' > CD tab > Add GitOps Source
   ID             : $GITOPS_SOURCE_NAME
   Repository URL : https://github.com/$GITHUB_OWNER/$APP_REPO
   Git Ref Type   : Branch -> main
   Path           : ./deploy
EOF
