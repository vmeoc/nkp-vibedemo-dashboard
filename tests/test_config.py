"""Tests for dashboard/config.py (ticket T01). DO NOT MODIFY."""
import tempfile
import unittest
from pathlib import Path

from dashboard import config


class ParseEnvFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env_file = Path(self.tmp.name) / ".env"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        self.env_file.write_text(text)

    def test_simple_values(self):
        self.write("A=1\nB=hello\n")
        self.assertEqual(config.parse_env_file(self.env_file), {"A": "1", "B": "hello"})

    def test_ignores_comments_blank_lines_and_lines_without_equal(self):
        self.write("# comment\n\nA=1\nnot a pair\n   # indented comment\n")
        self.assertEqual(config.parse_env_file(self.env_file), {"A": "1"})

    def test_strips_spaces_quotes_and_export(self):
        self.write('export A = "quoted value" \nB=\'single\'\nC=  spaced  \n')
        self.assertEqual(
            config.parse_env_file(self.env_file),
            {"A": "quoted value", "B": "single", "C": "spaced"},
        )

    def test_splits_on_first_equal_only(self):
        self.write("URL=http://x/?a=b\n")
        self.assertEqual(config.parse_env_file(self.env_file), {"URL": "http://x/?a=b"})

    def test_empty_value(self):
        self.write("SIM_FAIL_STEP=\n")
        self.assertEqual(config.parse_env_file(self.env_file), {"SIM_FAIL_STEP": ""})

    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(config.parse_env_file(Path(self.tmp.name) / "nope"), {})


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env_file = Path(self.tmp.name) / ".env"

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_when_no_file_and_empty_environ(self):
        cfg = config.load_config(env_file=Path(self.tmp.name) / "missing", environ={})
        self.assertEqual(cfg.state_file, config.REPO_ROOT / "state" / "run.json")
        self.assertEqual(cfg.app_url, "http://localhost")
        self.assertEqual(cfg.mode, "simulated")
        self.assertEqual(cfg.port, 8080)
        self.assertIsNone(cfg.sim_fail_step)

    def test_values_from_file(self):
        state = Path(self.tmp.name) / "s" / "run.json"
        self.env_file.write_text(
            f"STATE_FILE={state}\nAPP_URL=http://10.0.0.5\n"
            "DASHBOARD_MODE=live\nDASHBOARD_PORT=9000\nSIM_FAIL_STEP=deployment\n"
        )
        cfg = config.load_config(env_file=self.env_file, environ={})
        self.assertEqual(cfg.state_file, state)
        self.assertEqual(cfg.app_url, "http://10.0.0.5")
        self.assertEqual(cfg.mode, "live")
        self.assertEqual(cfg.port, 9000)
        self.assertEqual(cfg.sim_fail_step, "deployment")

    def test_environ_overrides_file(self):
        self.env_file.write_text("DASHBOARD_PORT=9000\nAPP_URL=http://file\n")
        cfg = config.load_config(env_file=self.env_file, environ={"DASHBOARD_PORT": "7000"})
        self.assertEqual(cfg.port, 7000)
        self.assertEqual(cfg.app_url, "http://file")

    def test_empty_sim_fail_step_is_none(self):
        self.env_file.write_text("SIM_FAIL_STEP=\n")
        cfg = config.load_config(env_file=self.env_file, environ={})
        self.assertIsNone(cfg.sim_fail_step)

    def test_state_file_expands_user_home(self):
        self.env_file.write_text("STATE_FILE=~/x/run.json\n")
        cfg = config.load_config(env_file=self.env_file, environ={})
        self.assertEqual(cfg.state_file, Path.home() / "x" / "run.json")

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            config.load_config(env_file=self.env_file, environ={"DASHBOARD_MODE": "magic"})

    def test_invalid_port_raises(self):
        with self.assertRaises(ValueError):
            config.load_config(env_file=self.env_file, environ={"DASHBOARD_PORT": "abc"})

    def test_config_is_immutable(self):
        cfg = config.load_config(env_file=self.env_file, environ={})
        with self.assertRaises(Exception):
            cfg.port = 1


if __name__ == "__main__":
    unittest.main()
