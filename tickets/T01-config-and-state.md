# T01 — Configuration and state file

## Goal

Two small modules: one reads the configuration, one reads and writes the
state file. No HTTP, no UI.

## Files

- CREATE `dashboard/config.py`
- CREATE `dashboard/state.py`

Do not create or change any other file.

## Read first

- `docs/SPEC.md` sections 4 and 5
- `tests/test_config.py`
- `tests/test_state.py`

## What to build

### `dashboard/config.py`

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_MODES = ("simulated", "live")

@dataclass(frozen=True)
class Config:
    state_file: Path
    app_url: str
    mode: str
    port: int
    sim_fail_step: str | None

def parse_env_file(path: Path) -> dict[str, str]: ...
def load_config(env_file: Path | None = None,
                environ: Mapping[str, str] | None = None) -> Config: ...
```

`load_config` steps, in this order:
1. `values = parse_env_file(env_file)` (default file: `REPO_ROOT / ".env"`)
2. `values.update(environ)` (default: `os.environ`)
3. Build each field from `values`, using the default when the key is missing
   OR empty (table in SPEC section 4).
4. `state_file`: `Path(os.path.expandvars(value)).expanduser()`.
5. Raise `ValueError` for a bad mode or a non-integer port.

Add `from __future__ import annotations` at the top so `str | None` works.

### `dashboard/state.py`

```python
VALID_PHASES = ("idle", "coding", "pushed")
def idle_state() -> dict: ...
def read_state(path: Path) -> dict: ...
def write_state(path: Path, state: dict) -> None: ...
```

- `read_state` must NEVER raise. Catch `json.JSONDecodeError`, `OSError`
  and `UnicodeDecodeError`.
- The result always has exactly the keys
  `phase`, `sha`, `started_at`, `pushed_at`, `warning`.
- Extra keys in the file (like `reset_at`) are dropped.
- `write_state`: create parent folders, write `run.json.tmp`, then
  `os.replace(tmp, path)`. JSON with `indent=2`.

## Done when

```
python3 -m unittest tests.test_config tests.test_state -v
```

prints `OK` at the end. Copy the last 5 lines of the output in your report.
