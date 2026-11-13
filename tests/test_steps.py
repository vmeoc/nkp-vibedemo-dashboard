"""Tests for dashboard/steps.py (ticket T02). DO NOT MODIFY."""
import unittest

from dashboard import steps

EXPECTED = [
    ("coding", "Code under development", "developer"),
    ("git_push", "Git push", "developer"),
    ("github_action", "GitHub Action", "developer"),
    ("contract_accepted", "Contract accepted", "nkp"),
    ("deployment", "Deployment", "nkp"),
    ("app_ready", "App is ready", "nkp"),
]


class StepsTest(unittest.TestCase):
    def test_definitions_order_labels_groups(self):
        self.assertEqual(
            [(d["id"], d["label"], d["group"]) for d in steps.STEP_DEFINITIONS],
            EXPECTED,
        )

    def test_step_ids(self):
        self.assertEqual(steps.STEP_IDS, tuple(e[0] for e in EXPECTED))

    def test_statuses(self):
        self.assertEqual(steps.STATUSES, ("pending", "running", "success", "failed"))

    def test_make_step_defaults(self):
        self.assertEqual(
            steps.make_step("git_push", "success"),
            {"id": "git_push", "label": "Git push", "group": "developer",
             "status": "success", "detail": "", "link": None},
        )

    def test_make_step_with_detail_and_link(self):
        step = steps.make_step("app_ready", "success", detail="App is available",
                               link="http://10.0.0.1")
        self.assertEqual(step["detail"], "App is available")
        self.assertEqual(step["link"], "http://10.0.0.1")
        self.assertEqual(step["group"], "nkp")

    def test_make_step_rejects_unknown_id(self):
        with self.assertRaises(ValueError):
            steps.make_step("nope", "success")

    def test_make_step_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            steps.make_step("coding", "great")

    def test_pending_steps(self):
        result = steps.pending_steps(detail="x")
        self.assertEqual([s["id"] for s in result], list(steps.STEP_IDS))
        self.assertTrue(all(s["status"] == "pending" for s in result))
        self.assertTrue(all(s["detail"] == "x" for s in result))

    def test_pending_steps_default_detail_is_empty(self):
        self.assertTrue(all(s["detail"] == "" for s in steps.pending_steps()))


if __name__ == "__main__":
    unittest.main()
