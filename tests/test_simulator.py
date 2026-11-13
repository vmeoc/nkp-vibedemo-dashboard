"""Tests for dashboard/simulator.py (ticket T02). DO NOT MODIFY."""
import unittest
from datetime import datetime, timedelta, timezone

from dashboard.simulator import simulate

PUSHED_AT = datetime(2026, 11, 13, 10, 0, 0, tzinfo=timezone.utc)
APP_URL = "http://10.0.0.100"
SHA = "3f2a9c1d8e7b6a5f4e3d2c1b0a9f8e7d6c5b4a39"


def pushed_state(pushed_at="2026-11-13T10:00:00+00:00", sha=SHA):
    return {"phase": "pushed", "sha": sha,
            "started_at": "2026-11-13T09:58:00+00:00", "pushed_at": pushed_at}


def statuses(result):
    return {s["id"]: s["status"] for s in result}


def at(seconds):
    return PUSHED_AT + timedelta(seconds=seconds)


class SimulatorTest(unittest.TestCase):
    def test_returns_six_steps_in_order(self):
        result = simulate(pushed_state(), at(0), APP_URL)
        self.assertEqual(
            [s["id"] for s in result],
            ["coding", "git_push", "github_action", "contract_accepted",
             "deployment", "app_ready"],
        )

    def test_idle_everything_pending(self):
        state = {"phase": "idle", "sha": None, "started_at": None, "pushed_at": None}
        result = simulate(state, at(100), APP_URL)
        self.assertTrue(all(s["status"] == "pending" for s in result))

    def test_coding(self):
        state = {"phase": "coding", "sha": None,
                 "started_at": "2026-11-13T09:58:00+00:00", "pushed_at": None}
        result = simulate(state, at(100), APP_URL)
        self.assertEqual(result[0]["status"], "running")
        self.assertEqual(result[0]["detail"], "AI is writing code")
        self.assertTrue(all(s["status"] == "pending" for s in result[1:]))

    def test_pushed_at_t0(self):
        result = simulate(pushed_state(), at(0), APP_URL)
        self.assertEqual(statuses(result), {
            "coding": "success", "git_push": "success", "github_action": "running",
            "contract_accepted": "pending", "deployment": "pending", "app_ready": "pending",
        })
        self.assertEqual(result[0]["detail"], "Code complete")
        self.assertEqual(result[1]["detail"], "Commit 3f2a9c1")
        self.assertEqual(result[2]["detail"], "In progress")

    def test_timeline_boundaries(self):
        expected = {
            19.9: ("running", "pending", "pending", "pending"),
            20: ("success", "running", "pending", "pending"),
            25: ("success", "success", "running", "pending"),
            34: ("success", "success", "running", "pending"),
            35: ("success", "success", "success", "running"),
            40: ("success", "success", "success", "success"),
            500: ("success", "success", "success", "success"),
        }
        for t, exp in expected.items():
            with self.subTest(t=t):
                st = statuses(simulate(pushed_state(), at(t), APP_URL))
                self.assertEqual(
                    (st["github_action"], st["contract_accepted"],
                     st["deployment"], st["app_ready"]),
                    exp,
                )

    def test_success_details_and_app_link(self):
        result = simulate(pushed_state(), at(40), APP_URL)
        by_id = {s["id"]: s for s in result}
        self.assertEqual(by_id["github_action"]["detail"], "Done")
        self.assertEqual(by_id["deployment"]["detail"], "Done")
        self.assertEqual(by_id["app_ready"]["detail"], "App is available")
        self.assertEqual(by_id["app_ready"]["link"], APP_URL)
        self.assertIsNone(by_id["github_action"]["link"])

    def test_z_suffix_timestamp(self):
        result = simulate(pushed_state(pushed_at="2026-11-13T10:00:00Z"), at(22), APP_URL)
        self.assertEqual(statuses(result)["contract_accepted"], "running")

    def test_missing_pushed_at_means_t0(self):
        result = simulate(pushed_state(pushed_at=None), at(1000), APP_URL)
        self.assertEqual(statuses(result)["github_action"], "running")

    def test_garbage_pushed_at_means_t0(self):
        result = simulate(pushed_state(pushed_at="yesterday"), at(1000), APP_URL)
        self.assertEqual(statuses(result)["github_action"], "running")

    def test_missing_sha(self):
        result = simulate(pushed_state(sha=None), at(0), APP_URL)
        self.assertEqual(result[1]["detail"], "Commit unknown")

    def test_fail_step_deployment(self):
        before = statuses(simulate(pushed_state(), at(30), APP_URL, fail_step="deployment"))
        self.assertEqual(before["deployment"], "running")
        result = simulate(pushed_state(), at(36), APP_URL, fail_step="deployment")
        by_id = {s["id"]: s for s in result}
        self.assertEqual(by_id["contract_accepted"]["status"], "success")
        self.assertEqual(by_id["deployment"]["status"], "failed")
        self.assertEqual(by_id["deployment"]["detail"], "Simulated failure")
        self.assertEqual(by_id["app_ready"]["status"], "pending")
        # still failed much later
        later = statuses(simulate(pushed_state(), at(999), APP_URL, fail_step="deployment"))
        self.assertEqual(later["deployment"], "failed")
        self.assertEqual(later["app_ready"], "pending")

    def test_fail_step_github_action(self):
        st = statuses(simulate(pushed_state(), at(999), APP_URL, fail_step="github_action"))
        self.assertEqual(st["github_action"], "failed")
        self.assertEqual(st["contract_accepted"], "pending")
        self.assertEqual(st["deployment"], "pending")
        self.assertEqual(st["app_ready"], "pending")

    def test_is_pure_same_input_same_output(self):
        a = simulate(pushed_state(), at(27), APP_URL)
        b = simulate(pushed_state(), at(27), APP_URL)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
