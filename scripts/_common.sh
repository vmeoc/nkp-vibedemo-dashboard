# Sourced by every script. Locates the repo, loads .env, sets defaults.
# shellcheck shell=bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PY="${PYTHON:-python3}"

MODE="${MODE:-simulated}"
APP_REPO="${APP_REPO:-vibe-demo-app}"
APP_REPO_DIR="${APP_REPO_DIR:-$ROOT/../$APP_REPO}"
case "$APP_REPO_DIR" in /*) ;; ~*) APP_REPO_DIR="${APP_REPO_DIR/#\~/$HOME}" ;; *) APP_REPO_DIR="$ROOT/$APP_REPO_DIR" ;; esac
NAMESPACE="${NAMESPACE:-vibe-demo}"
GITOPS_SOURCE="${GITOPS_SOURCE:-vibe-demo-app}"

kc() {
  # kubectl against the workload cluster that hosts the project namespace
  local args=()
  [ -n "${KUBECONFIG:-}" ] && args+=(--kubeconfig "$KUBECONFIG")
  [ -n "${KUBE_CONTEXT:-}" ] && args+=(--context "$KUBE_CONTEXT")
  kubectl ${args[@]+"${args[@]}"} "$@"   # bash 3.2-safe (macOS) empty-array expansion
}

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m OK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; exit 1; }
