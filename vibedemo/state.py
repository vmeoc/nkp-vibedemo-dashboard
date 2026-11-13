"""The run state file (state/run.json).

This is the ONLY state in the whole system, and only the AI's scripts write it:
  * status.sh coding  -> phase "coding"
  * push.sh           -> phase "pushed" + the commit SHA
  * raz.sh            -> phase "idle"
Everything after the push is observed from the real systems, never stored.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

PHASES = ("idle", "coding", "pushed")


def default_state() -> dict:
    return {
        "phase": "idle",
        "run_id": None,
        "started_at": None,
        "pushed_at": None,
        "sha": None,
        "message": None,
    }


def read_state(path: Path) -> dict:
    """Return the state. A missing or corrupted file means 'idle'."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_state()
    if not isinstance(data, dict) or data.get("phase") not in PHASES:
        return default_state()
    state = default_state()
    state.update({k: data.get(k) for k in state})
    return state


def write_state(path: Path, state: dict) -> None:
    """Atomic write: the dashboard never sees a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def new_run_id(now: float) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now))


def start_coding(path: Path, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    state = default_state()
    state.update({"phase": "coding", "run_id": new_run_id(now), "started_at": now})
    write_state(path, state)
    return state


def mark_pushed(path: Path, sha: str, message: str, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    state = read_state(path)
    if state["phase"] != "coding" or not state["run_id"]:
        # The AI forgot "status.sh coding": start the run now.
        state = default_state()
        state.update({"run_id": new_run_id(now), "started_at": now})
    state.update({"phase": "pushed", "pushed_at": now, "sha": sha, "message": message})
    write_state(path, state)
    return state


def reset(path: Path) -> dict:
    state = default_state()
    write_state(path, state)
    return state
