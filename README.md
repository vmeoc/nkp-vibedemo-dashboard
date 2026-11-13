# nkp-vibe-demo-dashboard

Platform toolkit for the demo **"a vibecoded app, automatically deployed on NKP"**.

An AI agent (Opencode, LLM served by Nutanix Enterprise AI) writes a static web
page, fills a **platform contract**, and pushes. The platform's golden path
builds the image, renders the Kubernetes manifests and Flux deploys them on NKP.
A **Pipeline Monitor** shows every step live.

```
 Opencode + NAI ──push──▶ GitHub (vibe-demo-app) ──▶ GitHub Actions (golden path, this repo)
       │                                               ├─ validate contract.yaml
       │                                               ├─ build + push ghcr.io/<owner>/vibe-demo-app:<sha>
       │                                               └─ render + commit deploy/
       │                                                          │
       └──── status.sh / diag.sh ──▶ Pipeline Monitor ◀── observes ── NKP project "vibe-demo"
                                                                   Flux ─▶ Deployment ─▶ LoadBalancer
```

## Two repositories, two lifecycles

| Repo | Changes | Content |
|---|---|---|
| **nkp-vibe-demo-dashboard** (this one) | at setup only | contract rules, renderer, golden-path workflow, scripts, dashboard |
| **vibe-demo-app** | every demo | `app/` + `contract.yaml` (AI), `deploy/` (written only by CI) |

The dashboard never runs in the same pod, namespace or repo as the demo app.

## Repository layout

```
vibedemo/            Python package (stdlib only, 3.9+)
  contract.py        contract parsing + platform rules
  render.py          contract -> Deployment + LoadBalancer Service
  state.py           state/run.json (the ONLY stored state, written by the AI scripts)
  sources.py         GitHub API, kubectl, HTTP (read-only)
  steps.py           the 6 steps, recomputed on every call (live + simulated)
  cli.py             entry point used by all scripts and by CI
dashboard/           Pipeline Monitor (server.py + static/index.html)
scripts/             vibe (the platform CLI) + status/validate/push/diag/raz/dashboard.sh
setup/               00..04 one-time setup + smoke test
docs/                step-by-step guide
app-template/        initial content of vibe-demo-app (baseline "Demo on hold")
.github/workflows/   build-deploy.yml (reusable golden path), tests.yml
tests/               unit tests: python3 -m unittest discover -s tests -t .
```

## How the dashboard stays reliable

* **No stored state.** `/api/status` recomputes the 6 steps from the real systems
  each time. Restart it whenever you want, it shows the right thing.
* **The AI declares only one thing:** that it is coding (`status.sh coding`).
  `push.sh` records the commit SHA. Everything after is observed.
* **One correlation key:** the commit SHA = image tag = Deployment label =
  content of `http://<LB-IP>/version.txt`. An old version can never be shown as the new one.
* **Deadlines:** a step that does not progress turns red with the last observed
  message (see `TIMEOUT_*` in `.env.example`).
* **Same code everywhere:** the dashboard, `diag.sh` and the AI (`diag.sh --wait`)
  use the same module. To troubleshoot, run `scripts/diag.sh`: you see exactly
  what the dashboard sees.

| Step | Source | Green when |
|---|---|---|
| Code under development | state file (AI) | the AI ran `status.sh coding` and then pushed |
| Git push | GitHub API | the commit exists on GitHub |
| GitHub Action | GitHub API (runs of `ci.yml` for this SHA) | run concluded `success` |
| Contract accepted | Flux Kustomization `GITOPS_SOURCE` | the `deploy:` commit for this SHA is applied and `Ready=True`. Red if Flux/admission refused it (message shown). When the deploy commit appears, the dashboard asks Flux to reconcile immediately (NKP polls GitHub every 3 min) |
| Deployment | Deployment labelled with the SHA | rollout complete, all replicas available |
| App is ready | Service LoadBalancer + HTTP | `/version.txt` returns the SHA |

## Setup (once)

**Full step-by-step guide with checkpoints: [docs/vibe-demo-app-guide.md](docs/vibe-demo-app-guide.md).**

Prerequisites: python3 (3.9+), git, kubectl, curl, opencode; an NKP cluster
with a LoadBalancer (MetalLB); a GitHub account.

1. **Put this repo on GitHub** as `<you>/nkp-vibe-demo-dashboard`, **public**
   (or private with *Settings > Actions > General > Access* open to your repos):
   the app repo calls its reusable workflow.
2. **Create an empty public repo** `<you>/vibe-demo-app` (no README).
3. **Create the token**: fine-grained, *only* `vibe-demo-app`, Contents R/W,
   Actions R/W, Workflows R/W (details in `.env.example`). Workflows is only
   needed by setup step 7 (it pushes `.github/workflows/`): remove it afterwards
   so the AI cannot change the pipeline.
4. `cp .env.example .env` and fill it. Keep `MODE=simulated` for now.
5. `setup/00-check-prereqs.sh`
6. `setup/01-create-project.sh` - creates the NKP Project with the fixed namespace
   `vibe-demo` (management cluster, `MGMT_KUBECONFIG`). The script validates the
   manifest with a server-side dry run first.
7. `setup/02-bootstrap-app-repo.sh` - creates `../vibe-demo-app` from
   `app-template/`, pushes the baseline + tag `baseline`, starts the on-hold image build.
8. **Make the GHCR package public** (link printed by step 7).
9. **NKP UI > Project vibe-demo > Continuous Deployment > Add GitOps Source**:
   ID `vibe-demo-app`, URL of the app repo, branch `main`, path `./deploy`.
10. `setup/03-check-gitops-source.sh` - checks Flux objects and the on-hold page.
11. `setup/04-install-cli.sh` - installs the `vibe` command (symlink in `~/.local/bin`).
    The AI only uses `vibe status|validate|push|diag`.
12. Set `MODE=live` in `.env`.

Whenever `app-template/AGENTS.md`, `CONTRACT.md` or `opencode.json` change,
run `setup/05-refresh-baseline.sh`: it updates vibe-demo-app and moves the
`baseline` tag (otherwise the next RAZ would restore the old files).

## The `vibe` CLI

```
vibe status coding|show|idle     tell the dashboard the AI is coding
vibe images "<subject>" [--count N]  free photos from Wikimedia Commons into app/images/
vibe validate [file]             check the contract against the platform rules
vibe push "<message>"            validate, commit, push, record the SHA
vibe diag [--wait|--watch|--json] pipeline status (same as the dashboard)
vibe raz [-y]                    reset the demo to "Demo on hold"
vibe dashboard                   start the Pipeline Monitor
```

Why a CLI and not scripts in the app repo: the AI cannot modify the platform
tools, the GitHub token stays in the platform `.env`, and the dashboard, `diag`
and the AI share exactly the same code.
12. `setup/04-smoke-test.sh` - the full chain without the AI (fixed test page),
    then `scripts/raz.sh -y`.

## Rehearse without infrastructure

```bash
# MODE=simulated in .env
vibe dashboard                          # open http://127.0.0.1:8090
vibe status coding                      # AI starts
vibe push "Hello page"                  # fake SHA, no GitHub call
vibe diag --wait                        # ~1 minute to "App is ready"
vibe raz -y                             # back to pending
SIMULATE_FAIL=deployment scripts/dashboard.sh   # rehearse a red step
```

## Running the demo

```bash
vibe raz -y                             # start clean: "Demo on hold"
vibe dashboard                          # second screen
cd ../vibe-demo-app && opencode         # the agent follows AGENTS.md
```

Ask for a page, e.g. *"Build a landing page for our Nutanix event in Paris with
a countdown, and deploy it."* The agent marks itself as coding, writes `app/`,
asks you the contract questions in plain words, shows the summary, waits for your
"yes", pushes and follows the deployment until it gives you the URL.

To reset between two demos, just tell the agent "reset the demo": it runs
`vibe raz -y` (allowed in opencode.json, and only on explicit request per
AGENTS.md). You only interact with Opencode; keep `vibe dashboard` running on
the second screen.

Photos: the agent runs `vibe images "<subject>"` once; files land in
`app/images/` and are baked into the container image (the deployed page does
not need Internet). A credits line is added in the footer.

## Troubleshooting

| Symptom | Look at |
|---|---|
| Anything | `scripts/diag.sh` (same view as the dashboard, with links) |
| GitHub Action red | the run link on the card; usually the contract (validated again in CI) |
| Contract accepted stays blue | `kubectl -n vibe-demo get kustomization` - is `GITOPS_SOURCE` the right name? |
| Contract accepted red | the message on the card is Flux's (e.g. admission webhook denied) |
| Deployment blue with ImagePullBackOff | GHCR package still private |
| App is ready blue | `kubectl -n vibe-demo get svc` - LoadBalancer IP pending? |
| Dashboard banner error | the backend exception is shown; run `scripts/diag.sh --json` |

## Next steps (not in this version)

* Admission policies (Kyverno/Gatekeeper) to show a platform refusal live.
* `backend-db` architectures (contract already knows them, refused as "not supported yet").
* Real OpenTelemetry injection and backup (today: labels only).
