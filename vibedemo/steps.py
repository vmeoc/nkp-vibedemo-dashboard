"""The six pipeline steps, recomputed from the real systems on every call.

Principles
  * Nothing is stored: status = f(state/run.json, GitHub, Kubernetes, HTTP).
  * One correlation key: the SHA of the commit pushed by the AI
    (image tag, Deployment label, /version.txt of the running app).
  * Steps are sequential: a step is only evaluated once the previous one
    succeeded. A failed step stops the chain.
  * Every step has a deadline (counted from the push). Past it, the step turns
    red with the last thing we observed - it never spins forever.

The only in-memory cache is "this step already succeeded for this SHA", which
spares GitHub API calls. Restarting the dashboard simply recomputes it.
"""

from __future__ import annotations

import threading
import time

from .sources import SourceError

STEPS = (
    ("coding", "Code under development", "ai"),
    ("git_push", "Git push", "github"),
    ("github_action", "GitHub Action", "github"),
    ("contract_accepted", "Contract accepted", "nkp"),
    ("deployment", "Deployment", "nkp"),
    ("app_ready", "App is ready", "nkp"),
)
STEP_IDS = tuple(s[0] for s in STEPS)

PENDING, RUNNING, SUCCESS, FAILED = "pending", "running", "success", "failed"
BAD_WAITING = ("ImagePullBackOff", "ErrImagePull", "CrashLoopBackOff",
               "CreateContainerConfigError", "InvalidImageName", "CreateContainerError")


def _short(sha) -> str:
    return (sha or "")[:7]


def _fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return "%dm%02ds" % (seconds // 60, seconds % 60) if seconds >= 60 else "%ds" % seconds


def _condition(obj: dict, ctype: str) -> dict:
    for cond in (obj.get("status") or {}).get("conditions") or []:
        if cond.get("type") == ctype:
            return cond
    return {}


class Evaluator:
    def __init__(self, cfg, sources=None, clock=time.time):
        self.cfg = cfg
        self.sources = sources
        self.clock = clock
        self._memo = {}          # (sha, step) -> step result (successes only)
        self._facts = {}         # (sha, name) -> value learned on the way (app name, url...)
        self._lock = threading.Lock()

    # ----------------------------------------------------------------- public
    def evaluate(self, state: dict) -> dict:
        with self._lock:
            now = self.clock()
            steps = {sid: self._step(sid, PENDING) for sid in STEP_IDS}
            phase = state.get("phase") or "idle"
            sha = state.get("sha")
            app_url = None

            if phase == "idle":
                steps["coding"]["detail"] = "Waiting for the AI to start"
            elif phase == "coding":
                started = state.get("started_at") or now
                steps["coding"] = self._step("coding", RUNNING, "AI is writing the code (%s)"
                                             % _fmt_duration(now - started))
            elif phase == "pushed" and sha:
                steps["coding"] = self._step("coding", SUCCESS, "Code written by the AI")
                pushed_at = state.get("pushed_at") or now
                if self.cfg.mode == "simulated":
                    self._simulate(steps, sha, now - pushed_at)
                else:
                    self._live(steps, sha, now - pushed_at)
                app_url = self._facts.get((sha, "app_url"))
                if steps["app_ready"]["status"] != SUCCESS:
                    app_url = None

            ordered = [steps[sid] for sid in STEP_IDS]
            started_at = state.get("started_at")
            finished = ordered[-1]["status"] == SUCCESS or any(s["status"] == FAILED for s in ordered)
            return {
                "mode": self.cfg.mode,
                "config": self.cfg.public_summary(),
                "run": {
                    "run_id": state.get("run_id"),
                    "phase": phase,
                    "sha": sha,
                    "short_sha": _short(sha),
                    "message": state.get("message"),
                    "started_at": started_at,
                    "pushed_at": state.get("pushed_at"),
                    "elapsed": (now - started_at) if started_at else None,
                    "finished": bool(phase == "pushed" and finished),
                },
                "steps": ordered,
                "app_url": app_url,
                "generated_at": now,
            }

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _step(sid: str, status: str, detail: str = "", link=None) -> dict:
        meta = dict((s[0], s) for s in STEPS)[sid]
        return {"id": sid, "label": meta[1], "group": meta[2], "status": status,
                "detail": detail, "link": link}

    def _deadline(self, steps, sid: str, elapsed: float) -> bool:
        """Turn a non-successful step red once its deadline has passed."""
        limit = self.cfg.timeouts.get(sid)
        step = steps[sid]
        if limit and elapsed > limit and step["status"] != SUCCESS:
            last = step["detail"] or "no progress observed"
            steps[sid] = self._step(sid, FAILED, "Timed out after %s - last seen: %s"
                                    % (_fmt_duration(limit), last), step["link"])
            return True
        return False

    def _remember(self, sha, sid, result):
        if result["status"] == SUCCESS:
            self._memo[(sha, sid)] = result
        return result

    # ------------------------------------------------------------------- live
    def _live(self, steps, sha, elapsed):
        checks = (
            ("git_push", self._check_git_push),
            ("github_action", self._check_github_action),
            ("contract_accepted", self._check_contract),
            ("deployment", self._check_deployment),
            ("app_ready", self._check_app_ready),
        )
        for sid, check in checks:
            cached = self._memo.get((sha, sid))
            if cached:
                steps[sid] = cached
                continue
            try:
                result = check(sha)
            except SourceError as exc:
                result = self._step(sid, RUNNING, str(exc))
            steps[sid] = self._remember(sha, sid, result)
            self._deadline(steps, sid, elapsed)
            if steps[sid]["status"] != SUCCESS:
                break

    def _check_git_push(self, sha):
        url = self.sources.commit_url(sha)
        if self.sources.commit_exists(sha):
            return self._step("git_push", SUCCESS, "Commit %s is on GitHub" % _short(sha), url)
        return self._step("git_push", RUNNING, "Waiting for commit %s on GitHub" % _short(sha))

    def _check_github_action(self, sha):
        runs = self.sources.workflow_runs(sha)
        if not runs:
            return self._step("github_action", RUNNING, "Waiting for the workflow to start")
        run = runs[0]
        link = run.get("html_url")
        status, conclusion = run.get("status"), run.get("conclusion")
        if status != "completed":
            text = "Building the image and rendering manifests" if status == "in_progress" \
                else "Workflow %s" % (status or "queued")
            return self._step("github_action", RUNNING, text, link)
        if conclusion == "success":
            return self._step("github_action", SUCCESS,
                              "Image %s:%s pushed, deploy/ rendered"
                              % (self.cfg.image_repository, _short(sha)), link)
        return self._step("github_action", FAILED, "Workflow finished: %s" % conclusion, link)

    def _check_contract(self, sha):
        deploy_sha = self._facts.get((sha, "deploy_sha"))
        if not deploy_sha:
            deploy_sha = self.sources.find_deploy_commit(sha)
            if not deploy_sha:
                return self._step("contract_accepted", RUNNING, "Waiting for the deploy/ commit")
            self._facts[(sha, "deploy_sha")] = deploy_sha
        ks = self.sources.kustomization()
        status = ks.get("status") or {}
        ready = _condition(ks, "Ready")
        applied = status.get("lastAppliedRevision") or ""
        attempted = status.get("lastAttemptedRevision") or ""
        message = (ready.get("message") or "").strip()
        if deploy_sha in applied and ready.get("status") == "True":
            return self._step("contract_accepted", SUCCESS,
                              "Flux applied revision %s" % _short(deploy_sha))
        if deploy_sha in attempted and ready.get("status") == "False":
            return self._step("contract_accepted", FAILED,
                              "Refused by the platform: %s" % message[:400])
        detail = "Flux has not picked up revision %s yet" % _short(deploy_sha)
        if ready.get("status") == "Unknown" and message:
            detail = "Flux: %s" % message[:200]
        return self._step("contract_accepted", RUNNING, detail)

    def _check_deployment(self, sha):
        deps = self.sources.deployments(sha)
        if not deps:
            return self._step("deployment", RUNNING, "Waiting for the Deployment")
        dep = deps[0]
        name = dep["metadata"]["name"]
        self._facts[(sha, "app")] = name
        spec, status = dep.get("spec") or {}, dep.get("status") or {}
        wanted = spec.get("replicas", 1)
        available = status.get("availableReplicas", 0) or 0
        updated = status.get("updatedReplicas", 0) or 0
        total = status.get("replicas", 0) or 0
        progressing = _condition(dep, "Progressing")
        if progressing.get("reason") == "ProgressDeadlineExceeded":
            return self._step("deployment", FAILED, "Rollout stuck: %s"
                              % (progressing.get("message") or "progress deadline exceeded"))
        done = (status.get("observedGeneration", 0) >= dep["metadata"].get("generation", 0)
                and updated == wanted and available == wanted and total == wanted)
        if done:
            return self._step("deployment", SUCCESS, "%s: %d/%d replicas ready" % (name, available, wanted))
        detail = "%s: %d/%d replicas ready" % (name, available, wanted)
        reasons = set()
        try:
            for pod in self.sources.pods(name, sha):
                for cs in (pod.get("status") or {}).get("containerStatuses") or []:
                    waiting = (cs.get("state") or {}).get("waiting") or {}
                    if waiting.get("reason") in BAD_WAITING:
                        reasons.add(waiting["reason"])
        except SourceError:
            pass
        if reasons:
            detail += " - pods: %s" % ", ".join(sorted(reasons))
        return self._step("deployment", RUNNING, detail)

    def _check_app_ready(self, sha):
        app = self._facts.get((sha, "app"))
        if not app:
            return self._step("app_ready", RUNNING, "Waiting for the Deployment")
        svc = self.sources.service(app)
        ingress = ((svc.get("status") or {}).get("loadBalancer") or {}).get("ingress") or []
        address = ingress and (ingress[0].get("ip") or ingress[0].get("hostname"))
        if not address:
            return self._step("app_ready", RUNNING, "Waiting for a LoadBalancer IP")
        url = "http://%s/" % address
        served = self.sources.http_get(url + "version.txt").strip()
        if served == sha:
            self._facts[(sha, "app_url")] = url
            return self._step("app_ready", SUCCESS, "Serving version %s at %s" % (_short(sha), url), url)
        return self._step("app_ready", RUNNING, "%s still serves version %s"
                          % (url, _short(served) or "unknown"), url)

    # -------------------------------------------------------------- simulated
    SIM_SCHEDULE = (            # step, seconds after push when it succeeds
        ("git_push", 2),
        ("github_action", 35),
        ("contract_accepted", 45),
        ("deployment", 58),
        ("app_ready", 64),
    )
    SIM_TEXT = {
        "git_push": ("Pushing commit", "Commit %s is on GitHub"),
        "github_action": ("Building the image and rendering manifests",
                          "Image %s:%s pushed, deploy/ rendered (simulated)"),
        "contract_accepted": ("Flux is reconciling", "Flux applied the manifests (simulated %s)"),
        "deployment": ("1/2 replicas ready", "2/2 replicas ready (simulated %s)"),
        "app_ready": ("Waiting for a LoadBalancer IP", "Serving version %s (simulated)"),
    }

    def _simulate(self, steps, sha, elapsed):
        elapsed *= self.cfg.simulate_speed
        fail = self.cfg.simulate_fail
        for sid, at in self.SIM_SCHEDULE:
            running_text, done_text = self.SIM_TEXT[sid]
            if sid == fail and elapsed >= at:
                steps[sid] = self._step(sid, FAILED, "Simulated failure (SIMULATE_FAIL=%s)" % sid)
                return
            if elapsed >= at:
                link = "http://192.0.2.10/" if sid == "app_ready" else None
                text = done_text % ((self.cfg.image_repository, _short(sha))
                                    if sid == "github_action" else _short(sha))
                steps[sid] = self._step(sid, SUCCESS, text, link)
                if sid == "app_ready":
                    self._facts[(sha, "app_url")] = link
            else:
                steps[sid] = self._step(sid, RUNNING, running_text)
                return
