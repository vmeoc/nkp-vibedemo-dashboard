#!/usr/bin/env bash
# Setup step 1 - create the NKP Project with a FIXED namespace name.
#
# The NKP UI appends 5 random characters to the project namespace
# (vibe-demo-x7k2p). Creating the Project as YAML with spec.namespaceName
# gives a stable name, so scripts and dashboard never need updating.
#
# Run against the MANAGEMENT cluster (MGMT_KUBECONFIG in .env).
# Settings used (.env): MGMT_KUBECONFIG, WORKSPACE_NAME, TARGET_CLUSTER,
#                       PROJECT_NAME, NAMESPACE, KUBECONFIG (workload, to verify)
set -euo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

PROJECT_NAME="${PROJECT_NAME:-vibe-demo}"
WORKSPACE_NAME="${WORKSPACE_NAME:-default-workspace}"
TARGET_CLUSTER="${TARGET_CLUSTER:-}"
[ -n "${MGMT_KUBECONFIG:-}" ] || die "set MGMT_KUBECONFIG in .env (kubeconfig of the NKP management cluster)"
MGMT_KUBECONFIG="${MGMT_KUBECONFIG/#\~/$HOME}"
mk() { kubectl --kubeconfig "$MGMT_KUBECONFIG" "$@"; }

log "Checking the management cluster"
mk get crd projects.workspaces.kommander.mesosphere.io >/dev/null 2>&1 \
  || die "Project CRD not found: is MGMT_KUBECONFIG the NKP management cluster (Ultimate/Kommander)?"

WS_NS="$(mk get workspaces.workspaces.kommander.mesosphere.io "$WORKSPACE_NAME" \
          -o jsonpath='{.status.namespaceRef.name}' 2>/dev/null || true)"
if [ -z "$WS_NS" ]; then
  warn "Workspace '$WORKSPACE_NAME' not found. Available workspaces (NAME / NAMESPACE):"
  mk get workspaces.workspaces.kommander.mesosphere.io \
    -o custom-columns=NAME:.metadata.name,NAMESPACE:.status.namespaceRef.name >&2 || true
  die "set WORKSPACE_NAME in .env"
fi
ok "Workspace $WORKSPACE_NAME -> namespace $WS_NS"

if [ -z "$TARGET_CLUSTER" ]; then
  warn "TARGET_CLUSTER is empty. Clusters of workspace $WORKSPACE_NAME:"
  mk -n "$WS_NS" get kommanderclusters.kommander.mesosphere.io -o custom-columns=NAME:.metadata.name >&2 || true
  die "set TARGET_CLUSTER in .env (the cluster that will run the demo app)"
fi

if mk -n "$WS_NS" get projects.workspaces.kommander.mesosphere.io "$PROJECT_NAME" >/dev/null 2>&1; then
  existing="$(mk -n "$WS_NS" get projects.workspaces.kommander.mesosphere.io "$PROJECT_NAME" \
               -o jsonpath='{.spec.namespaceName}')"
  ok "Project $PROJECT_NAME already exists (namespace: $existing) - nothing to do"
  [ "$existing" = "$NAMESPACE" ] || warn "NAMESPACE in .env is '$NAMESPACE' but the project uses '$existing': update .env"
  exit 0
fi

MANIFEST="$(cat <<EOF
apiVersion: workspaces.kommander.mesosphere.io/v1alpha1
kind: Project
metadata:
  name: ${PROJECT_NAME}
  namespace: ${WS_NS}
spec:
  workspaceRef:
    name: ${WORKSPACE_NAME}
  namespaceName: ${NAMESPACE}
  placement:
    clusters:
      - name: ${TARGET_CLUSTER}
EOF
)"

log "Validating the Project with a server-side dry run"
if ! printf '%s\n' "$MANIFEST" | mk apply --dry-run=server -f - ; then
  warn "The API server refused the manifest above. To see the fields of your NKP version:"
  warn "  kubectl --kubeconfig \$MGMT_KUBECONFIG explain projects.spec --api-version=workspaces.kommander.mesosphere.io/v1alpha1 --recursive"
  die "Project not created"
fi

log "Creating Project $PROJECT_NAME (namespace $NAMESPACE on cluster $TARGET_CLUSTER)"
printf '%s\n' "$MANIFEST" | mk apply -f -

log "Waiting for namespace $NAMESPACE on the workload cluster (max 120s)"
for _ in $(seq 1 40); do
  if kc get namespace "$NAMESPACE" >/dev/null 2>&1; then
    ok "Namespace $NAMESPACE is ready"
    echo
    echo "Next: in the NKP UI, open Project '$PROJECT_NAME' > Continuous Deployment (CD) > Add GitOps Source"
    echo "      (values printed by setup/02-bootstrap-app-repo.sh), then run setup/03-check-gitops-source.sh"
    exit 0
  fi
  sleep 3
done
warn "Namespace not visible yet on the workload cluster. Check KUBECONFIG (workload) and the project placement."
