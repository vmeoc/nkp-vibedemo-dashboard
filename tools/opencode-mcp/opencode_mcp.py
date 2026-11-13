"""opencode-mcp — let Claude (Desktop) drive a local Opencode agent.

Claude plans and verifies; Opencode (with the local LLM) writes the code.
The tools are designed to keep Claude's token usage LOW:
  - opencode runs in the background (start_task / get_task), so long runs
    never hit a tool-call timeout;
  - results are short summaries: exit code, changed files, log tail,
    test verdict + failing test names only.

Configuration (environment variables, set in claude_desktop_config.json):
  OPENCODE_REPO      absolute path of the repository Opencode works in (required)
  OPENCODE_BIN       path to the opencode binary (default: found on PATH / usual places)
  OPENCODE_TIMEOUT   max seconds for one Opencode task (default: 1200)

Run: uv run --with mcp python opencode_mcp.py   (stdio MCP server)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
TEST_TARGET = re.compile(r"^(tests(\.test_\w+)*)(\s+tests\.test_\w+)*$")
MAX_LOG_TAIL = 200

_lock = threading.Lock()
_procs: dict[str, subprocess.Popen] = {}


# --------------------------------------------------------------------------- config
def repo_dir() -> Path:
    """Return the repository directory from OPENCODE_REPO."""
    raw = os.environ.get("OPENCODE_REPO", "")
    if not raw:
        raise RuntimeError("OPENCODE_REPO is not set")
    path = Path(raw).expanduser().resolve()
    if not (path / ".git").exists():
        raise RuntimeError(f"OPENCODE_REPO is not a git repository: {path}")
    return path


def opencode_bin() -> str:
    """Locate the opencode binary."""
    configured = os.environ.get("OPENCODE_BIN")
    if configured:
        return configured
    found = shutil.which("opencode")
    if found:
        return found
    for candidate in ("~/.opencode/bin/opencode", "/opt/homebrew/bin/opencode",
                      "/usr/local/bin/opencode"):
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)
    raise RuntimeError("opencode binary not found: set OPENCODE_BIN")


def task_dir() -> Path:
    """Folder holding task logs and metadata (git-ignored)."""
    path = repo_dir() / ".orchestrator" / "tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------------- helpers
def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=repo_dir(), capture_output=True, text=True,
                          timeout=timeout)


def _changed_files() -> list[str]:
    out = _run(["git", "status", "--porcelain"]).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def _tail(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    text = ANSI.sub("", path.read_text(errors="replace"))
    return "\n".join(text.splitlines()[-lines:])


def _meta_path(task_id: str) -> Path:
    return task_dir() / f"{task_id}.json"


def _write_meta(task_id: str, meta: dict) -> None:
    _meta_path(task_id).write_text(json.dumps(meta, indent=2))


def _read_meta(task_id: str) -> dict:
    path = _meta_path(task_id)
    if not re.fullmatch(r"[0-9a-f]{8}", task_id) or not path.exists():
        raise ValueError(f"unknown task_id: {task_id}")
    return json.loads(path.read_text())


def _running_task() -> str | None:
    with _lock:
        for task_id, proc in _procs.items():
            if proc.poll() is None:
                return task_id
    return None


def _watchdog(task_id: str, proc: subprocess.Popen, timeout: int) -> None:
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        meta = _read_meta(task_id)
        meta["killed_reason"] = f"timeout after {timeout}s"
        _write_meta(task_id, meta)
        proc.wait()
    meta = _read_meta(task_id)
    meta["exit_code"] = proc.returncode
    meta["finished_at"] = time.time()
    _write_meta(task_id, meta)


# --------------------------------------------------------------------------- tools (plain functions)
def start_task(prompt: str, agent: str = "build", model: str = "") -> dict:
    """Start Opencode in the background on the repository. Returns a task_id."""
    busy = _running_task()
    if busy:
        return {"error": f"task {busy} is still running; wait or cancel it first"}
    if agent not in ("build", "plan"):
        return {"error": "agent must be 'build' or 'plan'"}
    task_id = uuid.uuid4().hex[:8]
    log_path = task_dir() / f"{task_id}.log"
    cmd = [opencode_bin(), "run", "--agent", agent]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    timeout = int(os.environ.get("OPENCODE_TIMEOUT", "1200"))
    log_file = open(log_path, "w")
    proc = subprocess.Popen(cmd, cwd=repo_dir(), stdout=log_file,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            start_new_session=True)
    log_file.close()
    with _lock:
        _procs[task_id] = proc
    _write_meta(task_id, {"task_id": task_id, "agent": agent, "model": model or None,
                          "prompt": prompt, "pid": proc.pid,
                          "started_at": time.time(), "exit_code": None})
    threading.Thread(target=_watchdog, args=(task_id, proc, timeout), daemon=True).start()
    return {"task_id": task_id, "status": "running"}


def get_task(task_id: str, tail_lines: int = 30) -> dict:
    """Status of a task: running/finished, exit code, changed files, log tail."""
    meta = _read_meta(task_id)
    with _lock:
        proc = _procs.get(task_id)
    running = proc is not None and proc.poll() is None
    end = time.time() if running else (meta.get("finished_at") or time.time())
    return {
        "task_id": task_id,
        "status": "running" if running else "finished",
        "exit_code": None if running else meta.get("exit_code"),
        "killed_reason": meta.get("killed_reason"),
        "elapsed_s": round(end - meta["started_at"]),
        "changed_files": _changed_files(),
        "log_tail": _tail(task_dir() / f"{task_id}.log",
                          max(1, min(tail_lines, MAX_LOG_TAIL))),
    }


def cancel_task(task_id: str) -> dict:
    """Stop a running task."""
    _read_meta(task_id)
    with _lock:
        proc = _procs.get(task_id)
    if proc is None or proc.poll() is not None:
        return {"task_id": task_id, "status": "not running"}
    os.killpg(proc.pid, signal.SIGTERM)
    meta = _read_meta(task_id)
    meta["killed_reason"] = "cancelled"
    _write_meta(task_id, meta)
    return {"task_id": task_id, "status": "cancelled"}


def run_tests(target: str = "") -> dict:
    """Run the unit tests; return only the verdict and failing test names."""
    target = target.strip()
    if target and not TEST_TARGET.fullmatch(target):
        return {"error": "target must look like 'tests.test_state' (space-separated allowed)"}
    cmd = [sys.executable, "-m", "unittest"]
    cmd += target.split() if target else ["discover", "-s", "tests", "-t", "."]
    proc = _run(cmd, timeout=300)
    output = proc.stdout + proc.stderr
    lines = output.splitlines()
    summary = [l for l in lines if l.startswith("Ran ") or l.startswith("OK")
               or l.startswith("FAILED")]
    failed = [l.split(":", 1)[1].strip() for l in lines
              if l.startswith("FAIL:") or l.startswith("ERROR:")]
    first_error = ""
    if failed:
        marker = next(i for i, l in enumerate(lines)
                      if l.startswith("FAIL:") or l.startswith("ERROR:"))
        first_error = "\n".join(lines[marker:marker + 25])
    return {"ok": proc.returncode == 0, "summary": " | ".join(summary),
            "failed_tests": failed[:20], "first_failure": first_error}


def git_status() -> dict:
    """Changed files and diff statistics (no file content)."""
    stat = _run(["git", "diff", "--stat", "HEAD"]).stdout.strip()
    last = _run(["git", "log", "--oneline", "-3"]).stdout.strip()
    return {"changed_files": _changed_files(), "diff_stat": stat, "last_commits": last}


def git_diff(path: str) -> dict:
    """Diff of ONE file against HEAD (use only when a failure needs it)."""
    if ".." in path or path.startswith("/"):
        return {"error": "path must be relative to the repository"}
    if Path(path).name.startswith(".env") and Path(path).name != ".env.example":
        return {"error": "refusing to show secret files"}
    diff = _run(["git", "diff", "HEAD", "--", path]).stdout
    if not diff and (repo_dir() / path).exists():
        diff = (repo_dir() / path).read_text(errors="replace")  # untracked file
    return {"path": path, "diff": diff[:20000], "truncated": len(diff) > 20000}


def git_commit(message: str) -> dict:
    """Stage everything and commit. Only call after the human approved."""
    if not message.strip():
        return {"error": "empty commit message"}
    _run(["git", "add", "-A"])
    proc = _run(["git", "commit", "-m", message])
    return {"ok": proc.returncode == 0,
            "output": (proc.stdout + proc.stderr).strip()[-2000:]}


# --------------------------------------------------------------------------- MCP wiring
def build_server():
    """Register the tools on a FastMCP server."""
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as Server

    server = Server("opencode")
    for func in (start_task, get_task, cancel_task, run_tests,
                 git_status, git_diff, git_commit):
        server.tool()(func)
    return server


if __name__ == "__main__":
    build_server().run()
