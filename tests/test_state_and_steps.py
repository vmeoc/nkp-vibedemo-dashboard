import tempfile
import unittest
from pathlib import Path

from vibedemo import state
from vibedemo.config import Config
from vibedemo.sources import SourceError
from vibedemo.steps import Evaluator

SHA = "a" * 40
DEPLOY_SHA = "b" * 40


def cfg(mode="live", **extra):
    env = {"MODE": mode, "GITHUB_TOKEN": "t", "GITHUB_OWNER": "me", "NAMESPACE": "vibe-demo"}
    env.update(extra)
    return Config(env=env, env_file=Path("/nonexistent"))


class FakeSources:
    def __init__(self):
        self.commit = True
        self.runs = [{"status": "completed", "conclusion": "success", "html_url": "https://gh/run/1"}]
        self.deploy_sha = DEPLOY_SHA
        self.ks = {"status": {"lastAppliedRevision": "main@sha1:" + DEPLOY_SHA,
                              "lastAttemptedRevision": "main@sha1:" + DEPLOY_SHA,
                              "conditions": [{"type": "Ready", "status": "True", "message": "Applied"}]}}
        self.deps = [{"metadata": {"name": "hello", "generation": 2},
                      "spec": {"replicas": 2},
                      "status": {"observedGeneration": 2, "replicas": 2, "updatedReplicas": 2,
                                 "availableReplicas": 2}}]
        self.pod_list = []
        self.svc = {"status": {"loadBalancer": {"ingress": [{"ip": "10.0.0.50"}]}}}
        self.served = SHA
        self.calls = 0

    def commit_exists(self, sha):
        self.calls += 1
        return self.commit

    def commit_url(self, sha):
        return "https://github.com/me/vibe-demo-app/commit/" + sha

    def workflow_runs(self, sha):
        return self.runs

    def find_deploy_commit(self, sha):
        return self.deploy_sha

    def kustomization(self):
        return self.ks

    def deployments(self, sha):
        return self.deps

    def pods(self, app, sha):
        return self.pod_list

    def service(self, app):
        return self.svc

    def http_get(self, url):
        if isinstance(self.served, Exception):
            raise self.served
        return self.served + "\n"


def pushed(now=1000.0):
    return {"phase": "pushed", "run_id": "r", "started_at": now - 60, "pushed_at": now - 10,
            "sha": SHA, "message": "m"}


def statuses(report):
    return [s["status"] for s in report["steps"]]


class StateTest(unittest.TestCase):
    def test_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "run.json")
            self.assertEqual(state.read_state(path)["phase"], "idle")
            state.start_coding(path, now=10)
            self.assertEqual(state.read_state(path)["phase"], "coding")
            st = state.mark_pushed(path, SHA, "msg", now=20)
            self.assertEqual((st["phase"], st["sha"], st["started_at"]), ("pushed", SHA, 10))
            path.write_text("{not json")
            self.assertEqual(state.read_state(path)["phase"], "idle")

    def test_push_without_coding_starts_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = state.mark_pushed(Path(tmp, "run.json"), SHA, "msg", now=50)
            self.assertEqual(st["started_at"], 50)


class LiveStepsTest(unittest.TestCase):
    def ev(self, src, now=1000.0):
        return Evaluator(cfg(), src, clock=lambda: now)

    def test_idle_and_coding(self):
        e = self.ev(FakeSources())
        self.assertEqual(statuses(e.evaluate(state.default_state())), ["pending"] * 6)
        r = e.evaluate({"phase": "coding", "started_at": 990.0})
        self.assertEqual(statuses(r)[0], "running")

    def test_full_success(self):
        r = self.ev(FakeSources()).evaluate(pushed())
        self.assertEqual(statuses(r), ["success"] * 6)
        self.assertEqual(r["app_url"], "http://10.0.0.50/")
        self.assertTrue(r["run"]["finished"])

    def test_success_is_cached(self):
        src = FakeSources()
        e = self.ev(src)
        e.evaluate(pushed())
        e.evaluate(pushed())
        self.assertEqual(src.calls, 1)

    def test_action_running_stops_chain(self):
        src = FakeSources()
        src.runs = [{"status": "in_progress", "conclusion": None, "html_url": "u"}]
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r), ["success", "success", "running", "pending", "pending", "pending"])

    def test_action_failure(self):
        src = FakeSources()
        src.runs = [{"status": "completed", "conclusion": "failure", "html_url": "u"}]
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[2], "failed")
        self.assertFalse(r["app_url"])

    def test_policy_refusal(self):
        src = FakeSources()
        src.ks = {"status": {"lastAppliedRevision": "main@sha1:old",
                             "lastAttemptedRevision": "main@sha1:" + DEPLOY_SHA,
                             "conditions": [{"type": "Ready", "status": "False",
                                             "message": "admission webhook denied the request"}]}}
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[3], "failed")
        self.assertIn("denied", r["steps"][3]["detail"])

    def test_flux_not_yet(self):
        src = FakeSources()
        src.ks["status"]["lastAppliedRevision"] = "main@sha1:old"
        src.ks["status"]["lastAttemptedRevision"] = "main@sha1:old"
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[3], "running")

    def test_deployment_progress_and_pod_reason(self):
        src = FakeSources()
        src.deps[0]["status"]["availableReplicas"] = 1
        src.pod_list = [{"status": {"containerStatuses": [{"state": {"waiting": {"reason": "ImagePullBackOff"}}}]}}]
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[4], "running")
        self.assertIn("ImagePullBackOff", r["steps"][4]["detail"])

    def test_deployment_deadline_exceeded(self):
        src = FakeSources()
        src.deps[0]["status"]["availableReplicas"] = 0
        src.deps[0]["status"]["conditions"] = [{"type": "Progressing", "status": "False",
                                                "reason": "ProgressDeadlineExceeded", "message": "stuck"}]
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[4], "failed")

    def test_old_version_still_served(self):
        src = FakeSources()
        src.served = "onhold"
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[5], "running")
        self.assertIn("onhold", r["steps"][5]["detail"])

    def test_source_error_then_timeout(self):
        src = FakeSources()
        src.served = SourceError("http://10.0.0.50/ not reachable yet")
        r = self.ev(src).evaluate(pushed())
        self.assertEqual(statuses(r)[5], "running")
        late = pushed()
        late["pushed_at"] = 1000.0 - 2000
        r = self.ev(src).evaluate(late)
        self.assertEqual(statuses(r)[5], "failed")
        self.assertIn("Timed out", r["steps"][5]["detail"])


class SimulatedStepsTest(unittest.TestCase):
    def test_progression(self):
        c = cfg(mode="simulated")
        st = pushed()
        r = Evaluator(c, None, clock=lambda: st["pushed_at"] + 40).evaluate(st)
        self.assertEqual(statuses(r), ["success", "success", "success", "running", "pending", "pending"])
        r = Evaluator(c, None, clock=lambda: st["pushed_at"] + 100).evaluate(st)
        self.assertEqual(statuses(r), ["success"] * 6)
        self.assertTrue(r["app_url"])

    def test_simulated_failure(self):
        c = cfg(mode="simulated", SIMULATE_FAIL="deployment")
        st = pushed()
        r = Evaluator(c, None, clock=lambda: st["pushed_at"] + 100).evaluate(st)
        self.assertEqual(statuses(r)[4], "failed")


if __name__ == "__main__":
    unittest.main()
