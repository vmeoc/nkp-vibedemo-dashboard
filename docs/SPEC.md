# Pipeline Monitor Dashboard — Specification

This is the reference for every ticket. If a ticket and this file disagree,
STOP and ask the human.

## 1. Purpose

A web page shown on screen during the "vibecoding on NKP" demo. It displays
six pipeline steps and their status, so the audience can follow:
the AI writes code -> it is pushed to GitHub -> GitHub Actions builds the image
-> NKP accepts the manifests -> the Deployment rolls out -> the app is reachable.

## 2. Design principles (do not break them)

1. **No database, no stored step status.** Every request to `/api/status`
   recomputes all steps from their sources. Restarting the server loses nothing.
2. **The AI writes only one thing:** the state file (`state/run.json`).
   Everything else is observed (simulated for now, real sources later).
3. **Never hide a problem.** Any error becomes a visible message
   (a `warning` field, a `failed` step, or a red banner in the UI).
   The server must never crash because of a bad state file.
4. **Python standard library only.** No pip install, no framework.
   Frontend: plain HTML + CSS + vanilla JavaScript, no build step.

## 3. Repository layout

```
nkp-vibedemo-dashboard/
├── AGENTS.md              rules for the coding agent
├── .env.example           configuration template (.env is never committed)
├── dashboard/
│   ├── __init__.py        (exists, empty)
│   ├── config.py          T01 — load configuration
│   ├── state.py           T01 — read/write the state file
│   ├── steps.py           T02 — step definitions and helpers
│   ├── simulator.py       T02 — simulated pipeline
│   ├── server.py          T03 — HTTP server
│   └── static/
│       ├── index.html     T03 placeholder, T04 real page
│       ├── app.js         T04
│       └── style.css      T04
├── tests/                 tests are GIVEN — never modify them
├── state/                 run.json lives here (git-ignored)
├── setup/                 one-time NKP setup scripts (do not modify)
├── scripts/               demo scripts (raz.sh — do not modify)
├── docs/SPEC.md           this file
└── tickets/               one file per task
```

Run the tests from the repository root:

```
python3 -m unittest discover -s tests -t . -v
```

Python 3.10 or newer.

## 4. Configuration (`dashboard/config.py`)

Read from a `.env` file at the repository root, then overridden by real
environment variables.

Module API:

```python
REPO_ROOT: Path            # parent folder of dashboard/
@dataclass(frozen=True)
class Config: state_file: Path; app_url: str; mode: str; port: int; sim_fail_step: str | None
def parse_env_file(path: Path) -> dict[str, str]: ...   # missing file -> {}
def load_config(env_file: Path | None = None,
                environ: Mapping[str, str] | None = None) -> Config: ...
```

`env_file=None` means `REPO_ROOT / ".env"`; `environ=None` means `os.environ`.
An empty value counts as "not set" (the default applies).

| Variable         | Field           | Type        | Default                     |
|------------------|-----------------|-------------|-----------------------------|
| `STATE_FILE`     | `state_file`    | `Path`      | `<repo>/state/run.json`     |
| `APP_URL`        | `app_url`       | `str`       | `http://localhost`          |
| `DASHBOARD_MODE` | `mode`          | `str`       | `simulated`                 |
| `DASHBOARD_PORT` | `port`          | `int`       | `8080`                      |
| `SIM_FAIL_STEP`  | `sim_fail_step` | `str\|None` | `None` (empty string = None)|

- `mode` must be `simulated` or `live`, otherwise `ValueError`.
- `port` must be an integer, otherwise `ValueError`.
- `state_file`: `~` and `$VARS` are expanded.

`.env` format: `KEY=VALUE` per line. Ignore blank lines and lines starting
with `#`. An optional leading `export ` is ignored. The value is stripped and
one pair of surrounding quotes (`"` or `'`) is removed. `$VAR` / `${VAR}` are
expanded with `os.path.expandvars`. Lines without `=` are ignored.
No inline comments.

## 5. State file (`state/run.json`)

Written by scripts (`status.sh`, `push.sh`, `raz.sh`), read by the dashboard.

```json
{
  "phase": "pushed",
  "sha": "3f2a9c1d8e7b6a5f4e3d2c1b0a9f8e7d6c5b4a39",
  "started_at": "2026-11-13T10:00:00+00:00",
  "pushed_at": "2026-11-13T10:02:30+00:00"
}
```

| Field        | Meaning                                              |
|--------------|------------------------------------------------------|
| `phase`      | `idle` \| `coding` \| `pushed`                       |
| `sha`        | full commit SHA pushed by the AI, or `null`          |
| `started_at` | when the AI started coding (ISO 8601, UTC), or `null`|
| `pushed_at`  | when the push happened (ISO 8601, UTC), or `null`    |

Extra keys may exist (e.g. `reset_at`, `baseline_sha`) and must be ignored.

Module API:

```python
VALID_PHASES = ("idle", "coding", "pushed")
def idle_state() -> dict: ...                 # a NEW dict every call
def read_state(path: Path) -> dict: ...
def write_state(path: Path, state: dict) -> None: ...
```

`idle_state()` returns
`{"phase": "idle", "sha": None, "started_at": None, "pushed_at": None}`.

`read_state` NEVER raises. It always returns a dict with exactly these keys:
`phase`, `sha`, `started_at`, `pushed_at`, `warning`.
- valid file -> values from the file (missing keys -> `None`), `warning: None`
- file missing -> idle state + `warning: "state file not found"`
- invalid JSON or not a JSON object -> idle state + `warning: "invalid state file"`
- unknown `phase` -> idle state + `warning: "unknown phase: <value>"`

Writing (`write_state`) is atomic: write `<file>.tmp`, then `os.replace`.
Parent directories are created if needed.

## 6. Steps (`dashboard/steps.py`)

Fixed order, fixed ids:

| # | id                  | label                    | group       |
|---|---------------------|--------------------------|-------------|
| 1 | `coding`            | Code under development   | `developer` |
| 2 | `git_push`          | Git push                 | `developer` |
| 3 | `github_action`     | GitHub Action            | `developer` |
| 4 | `contract_accepted` | Contract accepted        | `nkp`       |
| 5 | `deployment`        | Deployment               | `nkp`       |
| 6 | `app_ready`         | App is ready             | `nkp`       |

Status values: `pending`, `running`, `success`, `failed`.

A step is a dict:

```json
{
  "id": "github_action",
  "label": "GitHub Action",
  "group": "developer",
  "status": "running",
  "detail": "Building image",
  "link": null
}
```

`detail` is always a string (may be empty). `link` is a URL string or `null`.

Module API:

```python
STEP_DEFINITIONS   # tuple of dicts {"id", "label", "group"} in the order above
STEP_IDS           # tuple of the 6 ids in order
STATUSES = ("pending", "running", "success", "failed")
def make_step(step_id: str, status: str, detail: str = "", link: str | None = None) -> dict: ...
def pending_steps(detail: str = "") -> list[dict]: ...
```

`make_step` raises `ValueError` for an unknown id or status.

## 7. Simulated pipeline (`dashboard/simulator.py`)

`simulate(state, now, app_url, fail_step=None) -> list[dict]` — a PURE
function (no I/O, no clock: `now` is passed in). Returns the 6 steps in order.

- `coding`: idle -> `pending`; coding -> `running` ("AI is writing code");
  pushed -> `success` ("Code complete").
- `git_push`: idle/coding -> `pending`; pushed -> `success`
  ("Commit <first 7 chars of sha>"; if sha is missing: "Commit unknown").
- The 4 remaining steps only move when phase is `pushed`. Let
  `t = (now - pushed_at)` in seconds (`t = 0` if `pushed_at` is missing or
  unparsable). Timeline:

  | step                | running when      | success when |
  |---------------------|-------------------|--------------|
  | `github_action`     | 0 <= t < 20       | t >= 20      |
  | `contract_accepted` | 20 <= t < 25      | t >= 25      |
  | `deployment`        | 25 <= t < 35      | t >= 35      |
  | `app_ready`         | 35 <= t < 40      | t >= 40      |

  Before "running": `pending`. Details: running -> "In progress",
  success -> "Done", except `app_ready` success -> "App is available"
  with `link = app_url`.
- `fail_step`: if set to one of these 4 step ids, that step becomes `failed`
  ("Simulated failure") at the moment it would become `success`, and every
  step after it stays `pending`.
- ISO timestamps may end with `Z` or `+00:00`; both must parse.

## 8. HTTP API (`dashboard/server.py`)

Module API:

```python
def build_status(config: Config, now: datetime | None = None) -> dict: ...
def make_server(config: Config, port: int | None = None) -> ThreadingHTTPServer: ...
def main(argv: list[str] | None = None) -> None: ...
```

- `build_status`: `now` defaults to `datetime.now(timezone.utc)`.
- `make_server`: binds `127.0.0.1`; `port=None` means `config.port`;
  `port=0` means "any free port" (used by tests). Does not start serving.
- The request handler must call `build_status` through the module-level name
  at request time (tests replace it to simulate a crash).

`GET /api/status` -> `200`, `application/json`, header
`Cache-Control: no-store`:

```json
{
  "run": {
    "phase": "pushed",
    "sha": "3f2a9c1...",
    "started_at": "...",
    "pushed_at": "...",
    "mode": "simulated",
    "warning": null
  },
  "steps": [ ...6 step dicts... ],
  "generated_at": "2026-11-13T10:02:41+00:00"
}
```

- `mode == "simulated"` -> steps from `simulate()`.
- `mode == "live"` -> not implemented yet: the 6 steps are `pending` with
  detail "Live mode not implemented yet".
- If building the status raises an exception: `500` with
  `{"error": "<message>"}`. The server keeps running.

`GET /` -> `dashboard/static/index.html`.
`GET /static/<name>` -> a file from `dashboard/static/` with the right
content type (`.html`, `.js`, `.css`). The path is URL-decoded first; anything
that resolves outside that folder (`..`, `%2e%2e`, `%2F`…), any other
extension, or any missing file -> `404`.
Anything else -> `404`.

Start: `python3 -m dashboard.server [--port N] [--mode simulated|live]`
(command-line options override the configuration).

## 9. Web page (T04)

Title: **NKP Vibecoding Demo — Pipeline Monitor**.
Layout inspired by the mockup: an "AI" block on the left, then two groups:
"Developer workflow" (steps 1–3) and "NKP" (steps 4–6).
Each card shows: label, status, detail, link (if any).
Colors: pending grey, running blue (pulsing), success green, failed red.
Header shows: mode, short SHA, last refresh time.
Polls `/api/status` every 2 seconds. If a request fails, show a red banner
"Dashboard server unreachable" (never show stale data silently).
