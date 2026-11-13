from __future__ import annotations

import json
import os
from pathlib import Path


VALID_PHASES = ("idle", "coding", "pushed")


def idle_state() -> dict:
    """Return a fresh idle state dict."""
    return {"phase": "idle", "sha": None, "started_at": None, "pushed_at": None}


def read_state(path: Path) -> dict:
    """Read the state file; never raises; always returns the full key set."""
    idle = idle_state()

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**idle, "warning": "state file not found"}
    except (OSError, UnicodeDecodeError):
        return {**idle, "warning": "invalid state file"}

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return {**idle, "warning": "invalid state file"}

    if not isinstance(data, dict):
        return {**idle, "warning": "invalid state file"}

    phase = data.get("phase", None)

    if phase not in VALID_PHASES:
        return {**idle, "warning": f"unknown phase: {phase}"}

    return {
        "phase": phase,
        "sha": data.get("sha", None),
        "started_at": data.get("started_at", None),
        "pushed_at": data.get("pushed_at", None),
        "warning": None,
    }


def write_state(path: Path, state: dict) -> None:
    """Atomically write the state file as JSON (indent=2)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.flush()
    os.replace(tmp, path)
