from __future__ import annotations


STEP_DEFINITIONS = (
    {"id": "coding", "label": "Code under development", "group": "developer"},
    {"id": "git_push", "label": "Git push", "group": "developer"},
    {"id": "github_action", "label": "GitHub Action", "group": "developer"},
    {"id": "contract_accepted", "label": "Contract accepted", "group": "nkp"},
    {"id": "deployment", "label": "Deployment", "group": "nkp"},
    {"id": "app_ready", "label": "App is ready", "group": "nkp"},
)

STEP_IDS = tuple(d["id"] for d in STEP_DEFINITIONS)

STATUSES = ("pending", "running", "success", "failed")

_BY_ID = {d["id"]: d for d in STEP_DEFINITIONS}


def make_step(step_id: str, status: str, detail: str = "",
              link: str | None = None) -> dict:
    """Return a new step dict with the given id, status, detail and link."""
    if step_id not in _BY_ID:
        raise ValueError(f"unknown step id: {step_id}")
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    definition = _BY_ID[step_id]
    return {
        "id": step_id,
        "label": definition["label"],
        "group": definition["group"],
        "status": status,
        "detail": detail,
        "link": link,
    }


def pending_steps(detail: str = "") -> list[dict]:
    """Return all six steps in order, each with status pending."""
    return [make_step(d["id"], "pending", detail=detail) for d in STEP_DEFINITIONS]
