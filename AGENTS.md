# AGENTS.md — rules for the coding agent

You work on **nkp-vibedemo-dashboard**: a small web dashboard that shows the
progress of a demo pipeline. Read `docs/SPEC.md` before any change: it is the
single source of truth.

## How a task works

1. The human gives you ONE ticket from `tickets/`. Do only that ticket.
2. Read the ticket, `docs/SPEC.md`, and the test file(s) the ticket names.
3. In Plan mode, list: the files you will create or change, and the functions
   you will write. Nothing else. Wait for approval.
4. Write the code.
5. Run the command given in the ticket under "Done when".
6. If a test fails, fix YOUR code and run the command again.
7. Finish with a short report:
   - files changed
   - the last lines of the test output (copy them, do not summarize)

## Hard rules

- **Language: English everywhere** — code, comments, docstrings, UI text,
  log messages, commit messages.
- **Python 3.10+ standard library only.** Never run `pip install`.
  Never add a dependency, a framework, or a build tool.
- **Frontend: plain HTML, CSS, vanilla JavaScript.** No CDN, no library.
- **Never modify anything in `tests/`.** If you think a test is wrong,
  STOP and explain why. Do not change the test to make it pass.
- **Only touch the files listed in the ticket.** Do not rename, move, or
  delete other files. Do not "improve" code outside the ticket.
- **Never touch** `setup/`, `scripts/`, `tools/`, `opencode.json`, `.env`, `.env.example`, `AGENTS.md`,
  `docs/`, `tickets/`.
- **Never read or print the content of `.env`.** It contains secrets.
- **Do not guess.** If the ticket or the spec is unclear, STOP and ask.
- **No placeholders**: no `TODO`, no `pass` left in place of logic,
  no fake implementation just to satisfy a test.
- **Never say a task is done if the tests have not passed.**

## Code style

- Small functions, one job each. Type hints on every function.
- A one-line docstring on every public function.
- Use `pathlib.Path` for paths.
- Use `datetime` objects with `timezone.utc`; ISO 8601 strings in JSON.
- Prefer clear code over clever code.

## Commands

Run all tests (from the repository root):

```
python3 -m unittest discover -s tests -t . -v
```

Run one test file:

```
python3 -m unittest tests.test_state -v
```

Start the dashboard:

```
python3 -m dashboard.server
```
