#!/usr/bin/env python3
"""Pipeline Monitor - a tiny read-only web server (stdlib only).

  GET /             the dashboard page
  GET /api/status   the six steps, recomputed on every call (same logic as diag.sh)
  GET /healthz      liveness

Run:  scripts/dashboard.sh   (or: python3 dashboard/server.py)
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vibedemo import state as state_mod  # noqa: E402
from vibedemo.config import Config  # noqa: E402
from vibedemo.sources import LiveSources  # noqa: E402
from vibedemo.steps import Evaluator  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"


def make_handler(cfg: Config, evaluator: Evaluator):
    class Handler(BaseHTTPRequestHandler):
        server_version = "vibedemo-dashboard/1.0"

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/status":
                try:
                    report = evaluator.evaluate(state_mod.read_state(cfg.state_file))
                    self._send(200, json.dumps(report).encode(), "application/json")
                except Exception as exc:  # never crash the page: show the error
                    body = json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)})
                    self._send(500, body.encode(), "application/json")
            elif path == "/healthz":
                self._send(200, b"ok\n", "text/plain")
            else:
                self._send(404, b"not found\n", "text/plain")

        def log_message(self, fmt, *args):  # keep the console quiet (polling every 2s)
            if not self.path.startswith("/api/status"):
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    return Handler


def main() -> int:
    try:
        cfg = Config()
    except ValueError as exc:
        print("config error: %s" % exc)
        return 1
    if cfg.mode == "live" and cfg.missing_live_settings():
        print("missing settings in .env for live mode: %s" % ", ".join(cfg.missing_live_settings()))
        return 1
    sources = LiveSources(cfg) if cfg.mode == "live" else None
    evaluator = Evaluator(cfg, sources)
    server = ThreadingHTTPServer((cfg.dashboard_host, cfg.dashboard_port), make_handler(cfg, evaluator))
    print("Pipeline Monitor (%s mode) on http://%s:%d  - Ctrl-C to stop"
          % (cfg.mode, cfg.dashboard_host, cfg.dashboard_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
