"""Command line entry point: python3 -m vibedemo.cli <command> ...

Commands used by the AI (through scripts/*.sh):
  status coding|idle|show     declare the AI is coding / reset / show the state
  validate [contract.yaml]    check the contract and print it in plain English
  push "<message>"            validate, commit, push, record the SHA
  diag [--json|--watch|--wait] show the six steps (same logic as the dashboard)

Commands used by the platform (CI and setup scripts):
  render --contract --image --sha --namespace --out
  template --src --dst --set KEY=VALUE ...
  dispatch <workflow-file>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import contract as contract_mod
from . import render as render_mod
from . import state as state_mod
from .config import Config
from .sources import GitHub, LiveSources, SourceError, git_auth_header
from .steps import FAILED, SUCCESS, Evaluator

ICONS = {"pending": "[  ]", "running": "[..]", "success": "[OK]", "failed": "[KO]"}


def _cfg() -> Config:
    try:
        return Config()
    except ValueError as exc:
        sys.exit("config error: %s" % exc)


def _require_live(cfg: Config):
    missing = cfg.missing_live_settings()
    if missing:
        sys.exit("missing settings in .env for live mode: %s" % ", ".join(missing))


# ------------------------------------------------------------------- status
def cmd_status(args) -> int:
    cfg = _cfg()
    if args.action == "coding":
        st = state_mod.start_coding(cfg.state_file)
        print("Run %s started - the dashboard now shows 'Code under development'." % st["run_id"])
    elif args.action == "idle":
        state_mod.reset(cfg.state_file)
        print("State reset to idle.")
    else:
        print(json.dumps(state_mod.read_state(cfg.state_file), indent=2))
    return 0


# ----------------------------------------------------------------- validate
def _validate_file(path: Path) -> tuple:
    if not path.is_file():
        return {}, ["contract file not found: %s" % path]
    return contract_mod.load(path)


def cmd_validate(args) -> int:
    cfg = _cfg()
    path = Path(args.contract) if args.contract else cfg.app_repo_dir / "contract.yaml"
    if not args.contract and cfg.mode == "simulated" and not path.is_file():
        path = Path(__file__).resolve().parent.parent / "app-template" / "contract.yaml"
    normalized, errors = _validate_file(path)
    if errors:
        print("CONTRACT REFUSED (%s):" % path)
        for err in errors:
            print("  - " + err)
        return 3
    print("CONTRACT OK (%s)" % path)
    for line in contract_mod.describe(normalized):
        print("  " + line)
    return 0


# --------------------------------------------------------------------- push
def _git(repo: Path, *args, extra=None, check=True) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo)] + (extra or []) + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        sys.exit("git %s failed: %s" % (" ".join(args), (proc.stderr or proc.stdout).strip()))
    return proc


def cmd_push(args) -> int:
    cfg = _cfg()
    repo = cfg.app_repo_dir
    contract_path = repo / "contract.yaml"
    if cfg.mode == "simulated" and not contract_path.is_file():
        # Rehearsal before setup/02: use the template's contract.
        contract_path = Path(__file__).resolve().parent.parent / "app-template" / "contract.yaml"
        print("(simulated) %s not created yet - using app-template/contract.yaml" % repo)
    normalized, errors = _validate_file(contract_path)
    if errors:
        print("PUSH CANCELLED - the contract is refused:")
        for err in errors:
            print("  - " + err)
        print("Fix contract.yaml (ask the user if needed), then run push again.")
        return 3

    if cfg.mode == "simulated":
        sha = hashlib.sha1(("%s%s" % (time.time(), args.message)).encode()).hexdigest()
        state_mod.mark_pushed(cfg.state_file, sha, args.message)
        print("SIMULATED push (MODE=simulated): nothing sent to GitHub.")
        print("SHA %s recorded. Follow the deployment with: vibe diag --wait" % sha)
        return 0

    _require_live(cfg)
    if not (repo / ".git").exists():
        sys.exit("%s is not a git repository (run setup/02-bootstrap-app-repo.sh)" % repo)
    _git(repo, "add", "-A")
    if _git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0:
        print("Nothing to commit: change app/ or contract.yaml first.")
        return 4
    _git(repo, "commit", "-m", args.message)
    auth = ["-c", "http.https://github.com/.extraheader=" + git_auth_header(cfg.github_token)]
    # The platform bot commits deploy/ on main after each build: replay our commit on top.
    _git(repo, "pull", "--rebase", "--quiet", "origin", "main", extra=auth)
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "push", "origin", "HEAD:main", extra=auth)
    state_mod.mark_pushed(cfg.state_file, sha, args.message)
    print("Pushed commit %s to %s (main)." % (sha, cfg.repo_full_name))
    print("Follow the deployment with: vibe diag --wait")
    return 0


# --------------------------------------------------------------------- diag
def _evaluate(cfg: Config, evaluator=None):
    if evaluator is None:
        sources = LiveSources(cfg) if cfg.mode == "live" else None
        evaluator = Evaluator(cfg, sources)
    return evaluator, evaluator.evaluate(state_mod.read_state(cfg.state_file))


def _print_report(report: dict) -> None:
    run = report["run"]
    elapsed = run["elapsed"]
    print("Run %s | phase %s | sha %s | elapsed %s | mode %s" % (
        run["run_id"] or "-", run["phase"], run["short_sha"] or "-",
        ("%ds" % elapsed) if elapsed is not None else "-", report["mode"]))
    for step in report["steps"]:
        line = "  %s %-24s %s" % (ICONS[step["status"]], step["label"], step["detail"])
        if step["link"]:
            line += "  <%s>" % step["link"]
        print(line)
    if report["app_url"]:
        print("APP URL: %s" % report["app_url"])


def cmd_diag(args) -> int:
    cfg = _cfg()
    if cfg.mode == "live":
        _require_live(cfg)
    evaluator, report = _evaluate(cfg)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    if not (args.watch or args.wait):
        _print_report(report)
        return 0

    # --watch: refresh forever. --wait: print changes until done (exit code tells the result).
    deadline = time.time() + args.timeout
    last = None
    while True:
        _, report = _evaluate(cfg, evaluator)
        signature = [(s["status"], s["detail"]) for s in report["steps"]]
        if args.watch:
            print("\033[2J\033[H", end="")
            _print_report(report)
        elif signature != last:
            changed = [s for s, old in zip(report["steps"], last or [None] * 6)
                       if old != (s["status"], s["detail"])
                       and not (s["status"] == "pending" and not s["detail"])]
            for step in changed:
                print("%s %s %-22s %s%s" % (time.strftime("%H:%M:%S"), ICONS[step["status"]],
                                             step["label"], step["detail"],
                                             ("  <%s>" % step["link"]) if step["link"] else ""))
            sys.stdout.flush()
        last = signature
        if args.wait:
            statuses = [s["status"] for s in report["steps"]]
            if report["run"]["phase"] != "pushed":
                print("No push recorded yet: run vibe push first.")
                return 2
            if statuses[-1] == SUCCESS:
                print("DEPLOYED: %s" % report["app_url"])
                return 0
            failed = [s for s in report["steps"] if s["status"] == FAILED]
            if failed:
                print("FAILED at step '%s': %s" % (failed[0]["label"], failed[0]["detail"]))
                return 1
            if time.time() > deadline:
                print("Still not finished after %ds." % args.timeout)
                return 2
        time.sleep(args.interval)


# ------------------------------------------------------------------- render
def cmd_render(args) -> int:
    normalized, errors = _validate_file(Path(args.contract))
    if errors:
        print("Contract refused:")
        for err in errors:
            print("  - " + err)
        return 3
    files = render_mod.render_all(normalized, args.image, args.sha, args.namespace)
    for path in render_mod.write_deploy_dir(args.out, files):
        print("wrote " + path)
    return 0


# ----------------------------------------------------------------- template
def cmd_template(args) -> int:
    """Copy a template tree, replacing __KEY__ placeholders in text files."""
    src, dst = Path(args.src), Path(args.dst)
    values = dict(item.split("=", 1) for item in args.set or [])
    if dst.exists() and any(dst.iterdir()):
        sys.exit("destination %s is not empty" % dst)
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    for path in dst.rglob("*"):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            new = text
            for key, value in values.items():
                new = new.replace("__%s__" % key, value)
            if new != text:
                path.write_text(new, encoding="utf-8")
    print("template copied to %s" % dst)
    return 0


# ----------------------------------------------------------------- dispatch
def cmd_dispatch(args) -> int:
    cfg = _cfg()
    _require_live(cfg)
    gh = GitHub(cfg.github_token, cfg.github_owner, cfg.app_repo)
    for attempt in range(1, args.retries + 1):
        try:
            gh.dispatch_workflow(args.workflow, args.ref)
            print("Workflow %s started on %s. Follow it at https://github.com/%s/actions"
                  % (args.workflow, cfg.repo_full_name, cfg.repo_full_name))
            return 0
        except SourceError as exc:
            print("attempt %d/%d: %s" % (attempt, args.retries, exc))
            time.sleep(5)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vibedemo")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status")
    p.add_argument("action", choices=["coding", "idle", "show"])
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("validate")
    p.add_argument("contract", nargs="?")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("push")
    p.add_argument("message")
    p.set_defaults(func=cmd_push)

    p = sub.add_parser("diag")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true")
    group.add_argument("--watch", action="store_true")
    group.add_argument("--wait", action="store_true")
    p.add_argument("--interval", type=float, default=3.0)
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(func=cmd_diag)

    p = sub.add_parser("render")
    p.add_argument("--contract", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("template")
    p.add_argument("--src", required=True)
    p.add_argument("--dst", required=True)
    p.add_argument("--set", action="append")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("dispatch")
    p.add_argument("workflow")
    p.add_argument("--ref", default="main")
    p.add_argument("--retries", type=int, default=6)
    p.set_defaults(func=cmd_dispatch)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
