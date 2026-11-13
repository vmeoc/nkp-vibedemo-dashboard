# T03 — HTTP server

## Goal

A small HTTP server (standard library `http.server`) that serves the JSON
status and the static files.

## Files

- CREATE `dashboard/server.py`
- CREATE `dashboard/static/index.html` — a PLACEHOLDER only, exactly:

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>Pipeline Monitor</title></head>
<body><p>Placeholder — the real page comes in T04.</p></body></html>
```

Do not create or change any other file.

## Read first

- `docs/SPEC.md` section 8
- `tests/test_server.py`
- `dashboard/config.py`, `dashboard/state.py`, `dashboard/simulator.py`,
  `dashboard/steps.py` (use them, do not change them)

## What to build

```python
STATIC_DIR = Path(__file__).resolve().parent / "static"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}

def build_status(config: Config, now: datetime | None = None) -> dict: ...
def make_handler(config: Config) -> type[BaseHTTPRequestHandler]: ...
def make_server(config: Config, port: int | None = None) -> ThreadingHTTPServer: ...
def main(argv: list[str] | None = None) -> None: ...

if __name__ == "__main__":
    main()
```

### `build_status`

1. `now = now or datetime.now(timezone.utc)`
2. `st = state.read_state(config.state_file)`
3. steps: `simulate(st, now, config.app_url, config.sim_fail_step)` in
   simulated mode, `pending_steps("Live mode not implemented yet")` in live mode.
4. Return:

```python
{
    "run": {"phase": ..., "sha": ..., "started_at": ..., "pushed_at": ...,
            "mode": config.mode, "warning": st["warning"]},
    "steps": steps,
    "generated_at": now.isoformat(),
}
```

### Request handler (`make_handler` returns a class)

`do_GET`:
1. `path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)`
2. `/api/status` -> call `build_status(config)` inside `try/except Exception`.
   Success: 200 JSON. Exception: 500 JSON `{"error": str(exc)}`.
   Always send `Cache-Control: no-store` with JSON.
   IMPORTANT: call `build_status` by its module-level name inside `do_GET`
   (the tests replace it).
3. `/` -> serve `index.html`
4. starts with `/static/` -> serve the file named after `/static/`
5. anything else -> 404

Serving a file safely:

```python
target = (STATIC_DIR / name).resolve()
if target.parent != STATIC_DIR or not target.is_file() or target.suffix not in CONTENT_TYPES:
    -> 404
```

Always send `Content-Type` and `Content-Length`.
Override `log_message` to do nothing (quiet tests).

### `make_server`

`ThreadingHTTPServer(("127.0.0.1", port), make_handler(config))`,
where `port = config.port if port is None else port`.

### `main`

`argparse` with `--port` (int) and `--mode` (choices `simulated`, `live`).
`cfg = load_config()`, then override with `dataclasses.replace` when an
option is given. Print `Dashboard running on http://localhost:<port> (mode: <mode>)`,
then `serve_forever()`. Stop cleanly on Ctrl+C (`KeyboardInterrupt`).

## Done when

```
python3 -m unittest discover -s tests -t . -v
```

Only `tests.test_ui` may fail. Then a manual check:

```
python3 -m dashboard.server --port 8080
curl -s http://localhost:8080/api/status
```

prints the JSON with 6 steps. Copy the last 5 lines of the test output and
the curl output in your report.
