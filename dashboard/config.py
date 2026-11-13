from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_MODES = ("simulated", "live")


@dataclass(frozen=True)
class Config:
    """Immutable dashboard configuration."""
    state_file: Path
    app_url: str
    mode: str
    port: int
    sim_fail_step: str | None


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict; missing file yields an empty dict."""
    result: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return result
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        value = os.path.expandvars(value)
        result[key] = value
    return result


def load_config(env_file: Path | None = None,
               environ: Mapping[str, str] | None = None) -> Config:
    """Load configuration from a .env file overridden by environment variables."""
    if env_file is None:
        env_file = REPO_ROOT / ".env"
    if environ is None:
        environ = os.environ

    values: dict[str, str] = parse_env_file(env_file)
    values.update(environ)

    state_file_raw = values.get("STATE_FILE", "")
    if state_file_raw == "":
        state_file = REPO_ROOT / "state" / "run.json"
    else:
        state_file = Path(os.path.expandvars(state_file_raw)).expanduser()

    app_url = values.get("APP_URL", "")
    if app_url == "":
        app_url = "http://localhost"

    mode = values.get("DASHBOARD_MODE", "")
    if mode == "":
        mode = "simulated"
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")

    port_raw = values.get("DASHBOARD_PORT", "")
    if port_raw == "":
        port = 8080
    else:
        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            raise ValueError(f"invalid port: {port_raw}")

    sim_fail_step = values.get("SIM_FAIL_STEP", "")
    if sim_fail_step == "":
        sim_fail_step = None

    return Config(
        state_file=state_file,
        app_url=app_url,
        mode=mode,
        port=port,
        sim_fail_step=sim_fail_step,
    )
