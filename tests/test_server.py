"""Tests for dashboard/server.py (ticket T03). DO NOT MODIFY."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dashboard import server, state
from dashboard.config import Config


def make_config(tmp, mode="simulated", fail=None):
    return Config(state_file=Path(tmp) / "run.json", app_url="http://10.0.0.100",
                  mode=mode, port=0, sim_fail_step=fail)


class BuildStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_state_file(self):
        cfg = make_config(self.tmp.name)
        result = server.build_status(cfg)
        self.assertEqual(result["run"]["phase"], "idle")
        self.assertEqual(result["run"]["mode"], "simulated")
        self.assertEqual(result["run"]["warning"], "state file not found")
        self.assertEqual(len(result["steps"]), 6)
        self.assertTrue(all(s["status"] == "pending" for s in result["steps"]))
        datetime.fromisoformat(result["generated_at"])  # must be ISO 8601

    def test_run_section_keys(self):
        cfg = make_config(self.tmp.name)
        result = server.build_status(cfg)
        self.assertEqual(set(result.keys()), {"run", "steps", "generated_at"})
        self.assertEqual(set(result["run"].keys()),
                         {"phase", "sha", "started_at", "pushed_at", "mode", "warning"})

    def test_simulated_uses_now(self):
        cfg = make_config(self.tmp.name)
        state.write_state(cfg.state_file, {
            "phase": "pushed", "sha": "abcdef1234",
            "started_at": "2026-11-13T09:58:00+00:00",
            "pushed_at": "2026-11-13T10:00:00+00:00",
        })
        now = datetime(2026, 11, 13, 10, 0, 50, tzinfo=timezone.utc)
        result = server.build_status(cfg, now=now)
        self.assertEqual(result["run"]["sha"], "abcdef1234")
        self.assertTrue(all(s["status"] == "success" for s in result["steps"]))

    def test_simulated_fail_step(self):
        cfg = make_config(self.tmp.name, fail="deployment")
        state.write_state(cfg.state_file, {
            "phase": "pushed", "sha": "abcdef1234", "started_at": None,
            "pushed_at": "2026-11-13T10:00:00+00:00",
        })
        now = datetime(2026, 11, 13, 10, 1, 0, tzinfo=timezone.utc)
        steps = {s["id"]: s["status"] for s in server.build_status(cfg, now=now)["steps"]}
        self.assertEqual(steps["deployment"], "failed")

    def test_live_mode_not_implemented(self):
        cfg = make_config(self.tmp.name, mode="live")
        result = server.build_status(cfg)
        self.assertEqual(result["run"]["mode"], "live")
        self.assertTrue(all(s["status"] == "pending" for s in result["steps"]))
        self.assertTrue(all(s["detail"] == "Live mode not implemented yet"
                            for s in result["steps"]))


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = make_config(self.tmp.name)
        self.httpd = server.make_server(self.cfg, port=0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def get(self, path):
        return urllib.request.urlopen(self.base + path, timeout=5)

    def test_api_status(self):
        with self.get("/api/status") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.headers["Content-Type"])
            self.assertEqual(resp.headers["Cache-Control"], "no-store")
            body = json.loads(resp.read())
        self.assertEqual(len(body["steps"]), 6)

    def test_api_status_reflects_state_changes_without_restart(self):
        state.write_state(self.cfg.state_file, {
            "phase": "coding", "sha": None,
            "started_at": datetime.now(timezone.utc).isoformat(), "pushed_at": None,
        })
        with self.get("/api/status") as resp:
            body = json.loads(resp.read())
        self.assertEqual(body["run"]["phase"], "coding")
        self.assertEqual(body["steps"][0]["status"], "running")

        pushed = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
        state.write_state(self.cfg.state_file, {
            "phase": "pushed", "sha": "abcdef1234", "started_at": None, "pushed_at": pushed,
        })
        with self.get("/api/status") as resp:
            body = json.loads(resp.read())
        self.assertTrue(all(s["status"] == "success" for s in body["steps"]))

    def test_index(self):
        with self.get("/") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers["Content-Type"])

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/nope")
        self.assertEqual(ctx.exception.code, 404)

    def test_missing_static_file_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/static/does-not-exist.js")
        self.assertEqual(ctx.exception.code, 404)

    def test_path_traversal_is_404(self):
        for path in ("/static/../server.py", "/static/..%2Fserver.py",
                     "/static/%2e%2e/server.py"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    self.get(path)
                self.assertEqual(ctx.exception.code, 404)

    def test_500_on_error_and_server_survives(self):
        original = server.build_status

        def boom(cfg, now=None):
            raise RuntimeError("kaboom")

        server.build_status = boom
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.get("/api/status")
            self.assertEqual(ctx.exception.code, 500)
            self.assertEqual(json.loads(ctx.exception.read()), {"error": "kaboom"})
        finally:
            server.build_status = original
        with self.get("/api/status") as resp:
            self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
