# T04 — Web page

## Goal

The page shown on screen during the demo. It polls `/api/status` every
2 seconds and renders the 6 steps.

## Files

- REPLACE `dashboard/static/index.html`
- CREATE `dashboard/static/app.js`
- CREATE `dashboard/static/style.css`

Do not create or change any other file. Do NOT change `server.py`.

## Read first

- `docs/SPEC.md` sections 8 and 9
- `tests/test_ui.py`
- Run the server and look at the JSON:
  `curl -s http://localhost:8080/api/status`

## Layout

```
+--------------------------------------------------------------------------+
| NKP Vibecoding Demo — Pipeline Monitor   mode: simulated  sha: 3f2a9c1   |
|                                          last refresh: 10:02:41          |
+--------------------------------------------------------------------------+
| [banner: red, hidden unless the server is unreachable]                   |
| [warning: orange, hidden unless run.warning is not null]                 |
+--------+-----------------------------------------------------------------+
|        |  Developer workflow                                             |
|        |  [Code under development] [Git push] [GitHub Action]            |
|   AI   |                                                                 |
|        |  NKP                                                            |
|        |  [Contract accepted] [Deployment] [App is ready]                |
+--------+-----------------------------------------------------------------+
```

Each card: label (bold), status text, detail, and a link "Open app" /
"Open" when `link` is not null (opens in a new tab).

## `index.html` (static skeleton)

- `<title>NKP Vibecoding Demo — Pipeline Monitor</title>`
- `<link rel="stylesheet" href="/static/style.css">`
- Elements with these ids: `mode`, `sha`, `last-refresh`, `banner`, `warning`,
  `group-developer`, `group-nkp`.
- An "AI" block on the left (static text "AI").
- `<script src="/static/app.js"></script>` at the end of `<body>`.

## `app.js`

Vanilla JavaScript only. Structure:

```javascript
const POLL_INTERVAL_MS = 2000;

async function fetchStatus() { /* fetch("/api/status", {cache: "no-store"}) */ }
function renderHeader(run, generatedAt) { /* mode, short sha (7 chars or "-"), time */ }
function renderWarning(warning) { /* show/hide #warning */ }
function renderSteps(steps) { /* rebuild #group-developer and #group-nkp */ }
function renderCard(step) { /* returns a DOM element */ }
function showBanner(message) { /* show #banner */ }
function hideBanner() { /* hide #banner */ }
async function refresh() { /* fetch + render; on ANY error -> showBanner("Dashboard server unreachable") */ }

refresh();
setInterval(refresh, POLL_INTERVAL_MS);
```

- Card CSS classes: `card` + `status-<status>` (e.g. `card status-running`).
- Build DOM with `document.createElement` and `textContent`
  (never `innerHTML` with data from the API).
- A non-200 response is an error too (show the banner).

## `style.css`

- Dark background, large readable text (it is projected on a screen).
- `.status-pending` grey, `.status-running` blue with a pulse animation,
  `.status-success` green, `.status-failed` red.
- Cards in a row, same width, wrap on small screens.
- `#banner` red, `#warning` orange; both hidden by default (`hidden` attribute
  or a CSS class).

## Done when

```
python3 -m unittest discover -s tests -t . -v
```

prints `OK` (ALL tests). Then the human checks in the browser:

1. `python3 -m dashboard.server` and open http://localhost:8080
   -> 6 grey cards, warning "state file not found".
2. In another terminal, simulate a run:

```
python3 -c "from datetime import datetime, timezone; from dashboard import state; from dashboard.config import load_config; state.write_state(load_config().state_file, {'phase':'pushed','sha':'3f2a9c1d8e7b','started_at':None,'pushed_at':datetime.now(timezone.utc).isoformat()})"
```

   -> cards turn blue then green one after the other within 40 seconds,
   "App is ready" shows a link.
3. Stop the server -> red banner "Dashboard server unreachable" within 2 seconds.
