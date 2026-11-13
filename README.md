# nkp-vibedemo-dashboard

Platform toolkit for the **"Vibecoding on NKP"** demo:

- a **Pipeline Monitor** dashboard shown on screen during the demo,
- the platform scripts the AI is allowed to use (`scripts/`),
- one-time NKP setup (`setup/`).

The vibecoded app itself lives in a separate repository: `vibe-demo-app`.

## Quick start

```
cp .env.example .env        # then fill in the values
python3 -m dashboard.server # http://localhost:8080
```

Python 3.10+, standard library only.

## One-time NKP setup

```
./setup/01-create-project.sh
```

Creates the NKP project `vibe-demo` with a fixed namespace, then tells you
what to enter for the GitOps Source in the NKP UI.

## Reset the demo

```
./scripts/raz.sh --wait
```

## Development workflow (Opencode)

The code is written by an AI coding agent, one ticket at a time.

1. Open a **new Opencode session** for each ticket (short context = fewer mistakes).
2. Paste: `Read AGENTS.md, then do tickets/T0X-....md. Start in Plan mode.`
3. Check the plan: it must only list the files named in the ticket.
4. Let it build, then run the "Done when" command yourself.
5. Green -> `git add -A && git commit -m "T0X: ..."`.
   Red after 2 attempts -> `git reset --hard`, report the error, split the ticket.

| Ticket | Content                     | Tests                              |
|--------|-----------------------------|------------------------------------|
| T01    | config + state file         | `test_config`, `test_state`        |
| T02    | step model + simulator      | `test_steps`, `test_simulator`     |
| T03    | HTTP server                 | `test_server`                      |
| T04    | web page                    | `test_ui` + check in the browser   |

Run all tests: `python3 -m unittest discover -s tests -t . -v`

Reference: `docs/SPEC.md`.
