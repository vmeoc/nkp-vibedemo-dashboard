# T02 — Step model and simulated pipeline

## Goal

Define the 6 pipeline steps, and a simulator that computes their status
from the state file content and the current time. Pure Python: no file
access, no clock, no HTTP.

## Files

- CREATE `dashboard/steps.py`
- CREATE `dashboard/simulator.py`

Do not create or change any other file.

## Read first

- `docs/SPEC.md` sections 6 and 7
- `tests/test_steps.py`
- `tests/test_simulator.py`

## What to build

### `dashboard/steps.py`

```python
STEP_DEFINITIONS = (
    {"id": "coding",            "label": "Code under development", "group": "developer"},
    {"id": "git_push",          "label": "Git push",               "group": "developer"},
    {"id": "github_action",     "label": "GitHub Action",          "group": "developer"},
    {"id": "contract_accepted", "label": "Contract accepted",      "group": "nkp"},
    {"id": "deployment",        "label": "Deployment",             "group": "nkp"},
    {"id": "app_ready",         "label": "App is ready",           "group": "nkp"},
)
STEP_IDS = tuple(d["id"] for d in STEP_DEFINITIONS)
STATUSES = ("pending", "running", "success", "failed")

def make_step(step_id: str, status: str, detail: str = "",
              link: str | None = None) -> dict: ...
def pending_steps(detail: str = "") -> list[dict]: ...
```

`make_step` returns a NEW dict with keys
`id, label, group, status, detail, link`. Raise `ValueError` for an unknown
id or status.

### `dashboard/simulator.py`

```python
TIMELINE = (
    ("github_action",      0, 20),
    ("contract_accepted", 20, 25),
    ("deployment",        25, 35),
    ("app_ready",         35, 40),
)

def simulate(state: dict, now: datetime, app_url: str,
             fail_step: str | None = None) -> list[dict]: ...
```

Write it with these helpers (keep each one short):

1. `_parse_time(value) -> datetime | None`
   Replace a trailing `Z` with `+00:00`, then `datetime.fromisoformat`.
   Return `None` for `None`, non-strings, or any `ValueError`.
2. `_elapsed_seconds(state, now) -> float`
   Seconds between `pushed_at` and `now`; `0.0` if `pushed_at` cannot be parsed.
3. `simulate`:
   - phase `idle` (or anything unknown) -> `pending_steps()`
   - phase `coding` -> coding `running` "AI is writing code", the rest `pending`
   - phase `pushed` -> coding `success` "Code complete",
     git_push `success` "Commit <sha[:7]>" (or "Commit unknown"),
     then loop over `TIMELINE`:

```
failed = False
for step_id, start, end in TIMELINE:
    if failed or t < start:           -> pending
    elif t < end:                     -> running, "In progress"
    elif step_id == fail_step:        -> failed, "Simulated failure"; failed = True
    elif step_id == "app_ready":      -> success, "App is available", link=app_url
    else:                             -> success, "Done"
```

Always return the 6 steps in `STEP_IDS` order.

## Done when

```
python3 -m unittest tests.test_steps tests.test_simulator -v
```

prints `OK`. Then run ALL tests (T01 must still pass):

```
python3 -m unittest discover -s tests -t . -v
```

At this stage only `tests.test_server` and `tests.test_ui` may fail
(they belong to T03 and T04). Copy the last 5 lines of both outputs in your report.
