from __future__ import annotations

from datetime import datetime

from dashboard.steps import STEP_IDS, make_step, pending_steps

TIMELINE = (
    ("github_action", 0, 20),
    ("contract_accepted", 20, 25),
    ("deployment", 25, 35),
    ("app_ready", 35, 40),
)


def _parse_time(value) -> datetime | None:
    """Parse an ISO 8601 timestamp, accepting a trailing Z."""
    if not isinstance(value, str):
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _elapsed_seconds(state: dict, now: datetime) -> float:
    """Seconds between state's pushed_at and now; 0.0 if unparsable."""
    if not isinstance(state, dict):
        return 0.0
    pushed_at = _parse_time(state.get("pushed_at"))
    if pushed_at is None:
        return 0.0
    try:
        return (now - pushed_at).total_seconds()
    except TypeError:
        return 0.0


def simulate(state: dict, now: datetime, app_url: str,
            fail_step: str | None = None) -> list[dict]:
    """Compute the six pipeline steps from state and the current time."""
    phase = state.get("phase") if isinstance(state, dict) else None

    if phase == "coding":
        result: list[dict] = []
        for step_id in STEP_IDS:
            if step_id == "coding":
                result.append(make_step(step_id, "running", "AI is writing code"))
            else:
                result.append(make_step(step_id, "pending"))
        return result

    if phase != "pushed":
        return pending_steps()

    sha = state.get("sha") if isinstance(state, dict) else None
    if isinstance(sha, str) and sha:
        commit_detail = "Commit " + sha[:7]
    else:
        commit_detail = "Commit unknown"

    t = _elapsed_seconds(state, now)

    result = [
        make_step("coding", "success", "Code complete"),
        make_step("git_push", "success", commit_detail),
    ]

    failed = False
    for step_id, start, end in TIMELINE:
        if failed or t < start:
            result.append(make_step(step_id, "pending"))
        elif t < end:
            result.append(make_step(step_id, "running", "In progress"))
        elif step_id == fail_step:
            result.append(make_step(step_id, "failed", "Simulated failure"))
            failed = True
        elif step_id == "app_ready":
            result.append(make_step(step_id, "success", "App is available",
                                   link=app_url))
        else:
            result.append(make_step(step_id, "success", "Done"))

    return result
