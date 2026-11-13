"""Tests for dashboard/state.py (ticket T01). DO NOT MODIFY."""
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import state

IDLE = {"phase": "idle", "sha": None, "started_at": None, "pushed_at": None}


class ReadStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "run.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_phases_constant(self):
        self.assertEqual(state.VALID_PHASES, ("idle", "coding", "pushed"))

    def test_missing_file(self):
        result = state.read_state(self.path)
        self.assertEqual(result["warning"], "state file not found")
        for key, value in IDLE.items():
            self.assertEqual(result[key], value)

    def test_invalid_json(self):
        self.path.write_text("{not json")
        result = state.read_state(self.path)
        self.assertEqual(result["warning"], "invalid state file")
        self.assertEqual(result["phase"], "idle")

    def test_json_but_not_an_object(self):
        self.path.write_text("[1, 2, 3]")
        result = state.read_state(self.path)
        self.assertEqual(result["warning"], "invalid state file")
        self.assertEqual(result["phase"], "idle")

    def test_unknown_phase(self):
        self.path.write_text(json.dumps({"phase": "dancing"}))
        result = state.read_state(self.path)
        self.assertEqual(result["warning"], "unknown phase: dancing")
        self.assertEqual(result["phase"], "idle")

    def test_valid_pushed_state(self):
        data = {
            "phase": "pushed",
            "sha": "abc1234def",
            "started_at": "2026-11-13T10:00:00+00:00",
            "pushed_at": "2026-11-13T10:02:30+00:00",
            "reset_at": "ignored extra key",
        }
        self.path.write_text(json.dumps(data))
        result = state.read_state(self.path)
        self.assertEqual(result["phase"], "pushed")
        self.assertEqual(result["sha"], "abc1234def")
        self.assertEqual(result["pushed_at"], "2026-11-13T10:02:30+00:00")
        self.assertIsNone(result["warning"])

    def test_missing_optional_keys_default_to_none(self):
        self.path.write_text(json.dumps({"phase": "coding"}))
        result = state.read_state(self.path)
        self.assertEqual(result["phase"], "coding")
        self.assertIsNone(result["sha"])
        self.assertIsNone(result["started_at"])
        self.assertIsNone(result["pushed_at"])
        self.assertIsNone(result["warning"])


class WriteStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_then_read_roundtrip_creates_parent_dirs(self):
        path = Path(self.tmp.name) / "a" / "b" / "run.json"
        data = {"phase": "coding", "sha": None,
                "started_at": "2026-11-13T10:00:00+00:00", "pushed_at": None}
        state.write_state(path, data)
        self.assertEqual(json.loads(path.read_text()), data)
        self.assertEqual(state.read_state(path)["phase"], "coding")

    def test_write_leaves_no_tmp_file(self):
        path = Path(self.tmp.name) / "run.json"
        state.write_state(path, dict(IDLE))
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir()), ["run.json"])

    def test_idle_state_helper(self):
        self.assertEqual(state.idle_state(), IDLE)
        # must return a new dict each time
        first = state.idle_state()
        first["phase"] = "coding"
        self.assertEqual(state.idle_state()["phase"], "idle")


if __name__ == "__main__":
    unittest.main()
