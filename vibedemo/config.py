"""Configuration: read from the process environment, completed by the .env file
at the repository root. Real environment variables always win over .env."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> dict:
    """Parse a simple KEY=VALUE file. Ignores blank lines and # comments.
    Surrounding single or double quotes are removed."""
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


class Config:
    """All settings in one place. See .env.example for documentation."""

    def __init__(self, env: dict | None = None, env_file: Path | None = None):
        merged = load_env_file(env_file if env_file is not None else ROOT / ".env")
        merged.update(os.environ if env is None else env)
        self.raw = merged
        g = merged.get

        self.mode = (g("MODE") or "simulated").strip().lower()
        if self.mode not in ("simulated", "live"):
            raise ValueError("MODE must be 'simulated' or 'live' (got %r)" % self.mode)

        # GitHub
        self.github_token = g("GITHUB_TOKEN") or ""
        self.github_owner = g("GITHUB_OWNER") or ""
        self.app_repo = g("APP_REPO") or "vibe-demo-app"
        self.platform_repo = g("PLATFORM_REPO") or (
            "%s/nkp-vibe-demo-dashboard" % self.github_owner if self.github_owner else "")
        self.ci_workflow_file = g("CI_WORKFLOW_FILE") or "ci.yml"
        app_dir = g("APP_REPO_DIR") or str(ROOT.parent / self.app_repo)
        self.app_repo_dir = Path(os.path.expanduser(app_dir))
        if not self.app_repo_dir.is_absolute():
            self.app_repo_dir = (ROOT / self.app_repo_dir).resolve()

        # Kubernetes / NKP (workload cluster where the project namespace lives)
        self.kubeconfig = os.path.expanduser(g("KUBECONFIG") or "")
        self.kube_context = g("KUBE_CONTEXT") or ""
        self.namespace = g("NAMESPACE") or "vibe-demo"
        self.gitops_source = g("GITOPS_SOURCE") or "vibe-demo-app"

        # Dashboard
        self.dashboard_host = g("DASHBOARD_HOST") or "127.0.0.1"
        self.dashboard_port = int(g("DASHBOARD_PORT") or "8090")
        state = g("STATE_FILE") or str(ROOT / "state" / "run.json")
        self.state_file = Path(os.path.expanduser(state))

        # Timeouts, in seconds, counted from the git push (cumulative).
        self.timeouts = {
            "git_push": int(g("TIMEOUT_GIT_PUSH") or "60"),
            "github_action": int(g("TIMEOUT_GITHUB_ACTION") or "420"),
            "contract_accepted": int(g("TIMEOUT_CONTRACT_ACCEPTED") or "600"),
            "deployment": int(g("TIMEOUT_DEPLOYMENT") or "720"),
            "app_ready": int(g("TIMEOUT_APP_READY") or "780"),
        }

        # Simulation knobs (MODE=simulated only)
        self.simulate_fail = (g("SIMULATE_FAIL") or "").strip()
        self.simulate_speed = float(g("SIMULATE_SPEED") or "1")

    # ------------------------------------------------------------------ helpers
    @property
    def repo_full_name(self) -> str:
        return "%s/%s" % (self.github_owner, self.app_repo)

    @property
    def image_repository(self) -> str:
        return "ghcr.io/%s/%s" % (self.github_owner.lower(), self.app_repo.lower())

    def missing_live_settings(self) -> list:
        """Settings required in live mode that are not set."""
        missing = []
        if not self.github_token:
            missing.append("GITHUB_TOKEN")
        if not self.github_owner:
            missing.append("GITHUB_OWNER")
        return missing

    def public_summary(self) -> dict:
        """Safe-to-display settings (never includes the token)."""
        return {
            "mode": self.mode,
            "repo": self.repo_full_name,
            "namespace": self.namespace,
            "gitops_source": self.gitops_source,
        }
