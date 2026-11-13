"""Read-only access to the real systems: GitHub API, Kubernetes (kubectl), HTTP.

Every method returns plain facts (dicts, strings) or raises SourceError with a
human-readable message. No business logic here - that lives in steps.py.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


class SourceError(Exception):
    pass


# ---------------------------------------------------------------------- GitHub
class GitHub:
    API = "https://api.github.com"

    def __init__(self, token: str, owner: str, repo: str, timeout: float = 6.0):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.timeout = timeout

    def _request(self, method: str, path: str, params: dict | None = None, body=None):
        url = self.API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "vibedemo-dashboard")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read() or b"{}").get("message", "")
            except ValueError:
                detail = ""
            return exc.code, {"message": detail}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise SourceError("GitHub API unreachable: %s" % exc)

    def _repo(self) -> str:
        return "/repos/%s/%s" % (self.owner, self.repo)

    def commit_exists(self, sha: str) -> bool:
        status, body = self._request("GET", self._repo() + "/commits/" + sha)
        if status == 200:
            return True
        if status in (404, 422):
            return False
        raise SourceError("GitHub API error %s: %s" % (status, (body or {}).get("message")))

    def workflow_runs(self, workflow_file: str, sha: str) -> list:
        status, body = self._request(
            "GET", self._repo() + "/actions/workflows/%s/runs" % workflow_file,
            {"head_sha": sha, "per_page": 5})
        if status == 404:
            raise SourceError("workflow %s not found in %s/%s" % (workflow_file, self.owner, self.repo))
        if status != 200:
            raise SourceError("GitHub API error %s: %s" % (status, (body or {}).get("message")))
        return body.get("workflow_runs", [])

    def find_deploy_commit(self, source_sha: str):
        """The commit written by the golden-path workflow for source_sha."""
        status, body = self._request(
            "GET", self._repo() + "/commits", {"path": "deploy", "per_page": 20, "sha": "main"})
        if status != 200:
            raise SourceError("GitHub API error %s: %s" % (status, (body or {}).get("message")))
        for item in body or []:
            if source_sha in (item.get("commit", {}).get("message") or ""):
                return item["sha"]
        return None

    def dispatch_workflow(self, workflow_file: str, ref: str = "main") -> None:
        status, body = self._request(
            "POST", self._repo() + "/actions/workflows/%s/dispatches" % workflow_file,
            body={"ref": ref})
        if status != 204:
            raise SourceError("cannot start workflow %s (HTTP %s: %s)"
                              % (workflow_file, status, (body or {}).get("message")))

    def commit_url(self, sha: str) -> str:
        return "https://github.com/%s/%s/commit/%s" % (self.owner, self.repo, sha)


def git_auth_header(token: str) -> str:
    """Value for git's http.extraHeader, so the token never lands in .git/config."""
    raw = base64.b64encode(("x-access-token:%s" % token).encode()).decode()
    return "AUTHORIZATION: basic " + raw


# ------------------------------------------------------------------ Kubernetes
class Kube:
    def __init__(self, kubeconfig: str = "", context: str = "", namespace: str = "default",
                 timeout: float = 8.0):
        self.kubeconfig = kubeconfig
        self.context = context
        self.namespace = namespace
        self.timeout = timeout

    def _base(self) -> list:
        cmd = ["kubectl"]
        if self.kubeconfig:
            cmd += ["--kubeconfig", self.kubeconfig]
        if self.context:
            cmd += ["--context", self.context]
        return cmd + ["-n", self.namespace]

    def _run(self, args: list) -> str:
        try:
            proc = subprocess.run(self._base() + args, capture_output=True, text=True,
                                  timeout=self.timeout, env=os.environ.copy())
        except FileNotFoundError:
            raise SourceError("kubectl not found in PATH")
        except subprocess.TimeoutExpired:
            raise SourceError("kubectl timed out (cluster unreachable?)")
        if proc.returncode != 0:
            raise SourceError((proc.stderr or proc.stdout).strip().splitlines()[-1]
                              if (proc.stderr or proc.stdout).strip() else "kubectl failed")
        return proc.stdout

    def get_json(self, kind: str, name: str = "", selector: str = "") -> dict:
        args = ["get", kind]
        if name:
            args.append(name)
        if selector:
            args += ["-l", selector]
        return json.loads(self._run(args + ["-o", "json"]))

    def kustomization(self, name: str) -> dict:
        return self.get_json("kustomizations.kustomize.toolkit.fluxcd.io", name)

    def deployments(self, selector: str) -> list:
        return self.get_json("deployments", selector=selector).get("items", [])

    def pods(self, selector: str) -> list:
        return self.get_json("pods", selector=selector).get("items", [])

    def service(self, name: str) -> dict:
        return self.get_json("service", name)

    def request_reconcile(self, name: str) -> None:
        """Ask Flux to reconcile the GitRepository and Kustomization now
        (same annotation as `flux reconcile`)."""
        stamp = "reconcile.fluxcd.io/requestedAt=%d" % int(time.time())
        for kind in ("gitrepositories.source.toolkit.fluxcd.io",
                     "kustomizations.kustomize.toolkit.fluxcd.io"):
            self._run(["annotate", "--overwrite", "%s/%s" % (kind, name), stamp])


# ------------------------------------------------------------------------ HTTP
def http_get(url: str, timeout: float = 3.0) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise SourceError("HTTP %s on %s" % (exc.code, url))
    except (urllib.error.URLError, OSError) as exc:
        raise SourceError("%s not reachable yet (%s)" % (url, getattr(exc, "reason", exc)))


class LiveSources:
    """Bundles the three sources for the step evaluator (tests inject fakes)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.github = GitHub(cfg.github_token, cfg.github_owner, cfg.app_repo)
        self.kube = Kube(cfg.kubeconfig, cfg.kube_context, cfg.namespace)

    def commit_exists(self, sha):
        return self.github.commit_exists(sha)

    def commit_url(self, sha):
        return self.github.commit_url(sha)

    def workflow_runs(self, sha):
        return self.github.workflow_runs(self.cfg.ci_workflow_file, sha)

    def find_deploy_commit(self, sha):
        return self.github.find_deploy_commit(sha)

    def kustomization(self):
        return self.kube.kustomization(self.cfg.gitops_source)

    def deployments(self, sha):
        return self.kube.deployments("vibedemo.nutanix.com/sha=%s" % sha)

    def pods(self, app, sha):
        return self.kube.pods("app.kubernetes.io/name=%s,vibedemo.nutanix.com/sha=%s" % (app, sha))

    def service(self, app):
        return self.kube.service(app)

    def request_reconcile(self):
        self.kube.request_reconcile(self.cfg.gitops_source)

    def http_get(self, url):
        return http_get(url)
