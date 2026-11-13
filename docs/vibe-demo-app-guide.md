# vibe-demo-app — step-by-step setup guide

From zero to a working demo: the app repo on GitHub, deployed on NKP by Flux,
followed live by the dashboard. Each step ends with a **checkpoint**: do not go
further until it is OK.

Time needed: about 45 minutes the first time.

```
your laptop
├── nkp-vibe-demo-dashboard/   platform repo (this one)  -> github.com/<you>/nkp-vibe-demo-dashboard (public)
└── vibe-demo-app/             created by setup/02       -> github.com/<you>/vibe-demo-app (public)
```

Both folders must sit **side by side**: the AI calls `../nkp-vibe-demo-dashboard/scripts/*`.

---

## Step 0 — Prerequisites

On the laptop: `python3` (3.9+), `git`, `kubectl`, `curl`, `opencode` (already
configured with your NAI endpoint and model).

Network: the laptop must reach
* the **API of the workload cluster** (kubectl), and
* the **LoadBalancer IP range** of that cluster (the dashboard opens `http://<LB-IP>/version.txt`).

On NKP: a workload cluster attached to a workspace, with a working LoadBalancer
(MetalLB), and the kubeconfigs of the **management** cluster and of the **workload** cluster.

> If the folder is not called `nkp-vibe-demo-dashboard`, that is fine: setup/02
> writes the real folder name into the app repo. Only the GitHub name matters (step 1).

---

## Step 1 — Put the platform repo on GitHub

The app repo calls the platform's reusable workflow, so GitHub must be able to read it.

1. Push this repo to `github.com/<you>/nkp-vibe-demo-dashboard` (branch `main`).
2. Make it **public**. (Private is possible: repo *Settings > Actions > General >
   Access* -> "Accessible from repositories owned by the user".)

If the GitHub repo has another name, you will set `PLATFORM_REPO=<you>/<name>` in `.env` (step 4).

**Checkpoint:** `https://github.com/<you>/nkp-vibe-demo-dashboard/blob/main/.github/workflows/build-deploy.yml` opens.

---

## Step 2 — Create the empty app repo

github.com > **New repository**
* Name: `vibe-demo-app`
* **Public**
* **No** README, no .gitignore, no licence (it must be completely empty)

**Checkpoint:** the repo page shows "Quick setup — if you've done this kind of thing before".

---

## Step 3 — Create the GitHub token for the AI

github.com > Settings > Developer settings > **Fine-grained tokens** > Generate new token
* Expiration: until after your demo dates
* Repository access: **Only select repositories** -> `vibe-demo-app`
* Repository permissions:
  * **Contents**: Read and write
  * **Actions**: Read and write
  * Metadata: Read-only (added automatically)

Copy the token (`github_pat_...`). It only gives access to `vibe-demo-app`: the
AI cannot modify the platform repo.

---

## Step 4 — Fill `.env`

```bash
cd nkp-vibe-demo-dashboard
cp .env.example .env
```

Edit `.env`:

| Variable | Value |
|---|---|
| `MODE` | `simulated` for now |
| `GITHUB_TOKEN` | the token of step 3 |
| `GITHUB_OWNER` | your GitHub login |
| `PLATFORM_REPO` | only if the GitHub name is not `nkp-vibe-demo-dashboard` |
| `MGMT_KUBECONFIG` | path of the management cluster kubeconfig |
| `WORKSPACE_NAME` | NKP workspace (default `default-workspace`) |
| `TARGET_CLUSTER` | leave empty, step 6 lists the names |
| `KUBECONFIG` | uncomment and set to the **workload** cluster kubeconfig (or keep your shell's) |

Then:

```bash
setup/00-check-prereqs.sh
```

**Checkpoint:** no `!!` line except possibly "namespace vibe-demo not reachable".

---

## Step 5 — Rehearse the dashboard (no infrastructure)

Terminal 1:
```bash
scripts/dashboard.sh          # open http://127.0.0.1:8090
```
Terminal 2:
```bash
scripts/status.sh coding
scripts/push.sh "rehearsal"   # simulated: nothing sent to GitHub
scripts/diag.sh --wait        # about 1 minute to "App is ready"
scripts/raz.sh -y
```

**Checkpoint:** the six cards turn green one after the other, then go back to "Pending".

---

## Step 6 — Create the NKP project (fixed namespace `vibe-demo`)

```bash
setup/01-create-project.sh
```

The first run stops and lists the clusters of the workspace: copy the right name
into `TARGET_CLUSTER` in `.env`, then run it again. The script validates the
Project with a server-side dry run before creating it.

> If the dry run refuses a field, the error says which one. Show the schema of your
> NKP version with:
> `kubectl --kubeconfig $MGMT_KUBECONFIG explain projects.spec --api-version=workspaces.kommander.mesosphere.io/v1alpha1 --recursive`

**Checkpoint:** `Namespace vibe-demo is ready`, and the project `vibe-demo` appears in the NKP UI.

---

## Step 7 — Create and push vibe-demo-app

```bash
setup/02-bootstrap-app-repo.sh
```

It creates `../vibe-demo-app` from `app-template/`, renders the baseline
`deploy/` (image `:onhold`), commits `baseline: demo on hold [skip ci]`, tags it
`baseline`, pushes, and starts the **Build on-hold image** workflow.

**Checkpoint:**
* github.com/<you>/vibe-demo-app shows `app/`, `contract.yaml`, `deploy/`, `.github/`, tag `baseline`
* *Actions* tab: **Build on-hold image** is green (about 1 minute)

---

## Step 8 — Make the image public

github.com/<you>?tab=packages > `vibe-demo-app` > **Package settings** >
Danger Zone > **Change visibility** > **Public**.

(Without this, pods stay in `ImagePullBackOff`.)

**Checkpoint:** the package page shows "Public" and the tag `onhold`.

---

## Step 9 — Connect Flux: GitOps Source in the NKP project

NKP UI > Workspace > **Projects** > `vibe-demo` > **Continuous Deployment (CD)** > **Add GitOps Source**

| Field | Value |
|---|---|
| ID (name) | `vibe-demo-app` |
| Repository URL | `https://github.com/<you>/vibe-demo-app` |
| Git Ref Type | Branch -> `main` |
| Path | `./deploy` |

No secret needed (public repo).

```bash
setup/03-check-gitops-source.sh
```

**Checkpoint:** Kustomization `vibe-demo-app` Ready=True, a Deployment and a
Service `vibe-app`, and `On-hold page served at http://<IP>/`. Open that URL:
"Demo on hold". If the Kustomization has another name, put it in `GITOPS_SOURCE`.

---

## Step 10 — Switch to live and run the smoke test (no AI)

In `.env`: `MODE=live`. Restart the dashboard (Ctrl-C, `scripts/dashboard.sh`).

```bash
setup/04-smoke-test.sh
```

It does exactly what the AI will do, with a fixed test page. Watch the dashboard:
the six cards turn green in 2 to 4 minutes, and the page shows "Smoke test OK".

```bash
scripts/raz.sh -y
```

**Checkpoint:** smoke test green, then "Demo on hold" served again and dashboard back to "Pending".

> If a step fails, the card and `scripts/diag.sh` show why. See *Troubleshooting* below.

---

## Step 11 — First run with the AI

Terminal 1: `scripts/dashboard.sh` (dashboard on the second screen)

Terminal 2:
```bash
cd ../vibe-demo-app
opencode
```

Opencode reads `AGENTS.md` (procedure) and `opencode.json` (allowed commands).
First check that the guard rails work: ask it to run `ls -la /` -> allowed;
ask it to run `git log` -> it must be **refused**. If `git log` runs, fix the
`permission.bash` patterns in `vibe-demo-app/opencode.json` for your Opencode version.

Then the real request, for example:

> Build a landing page for our Nutanix event in Paris on March 12, with a
> countdown and a registration button, and deploy it.

Expected behaviour:
1. The **Code under development** card turns blue (`status.sh coding`).
2. It writes `app/index.html`.
3. It asks you the contract questions in plain words (environment, size, protection...).
4. It shows the summary from `validate.sh` and asks "Shall I deploy?".
5. You answer yes -> `push.sh` (Opencode asks you to approve this command).
6. It runs `diag.sh --wait`, cards turn green, it gives you the URL.

After the run: `scripts/raz.sh -y`.

---

## Demo day checklist

- [ ] VPN / network: `kubectl -n vibe-demo get pods` works from the laptop
- [ ] `scripts/raz.sh -y` -> "Demo on hold" served
- [ ] `scripts/dashboard.sh` open on the second screen, mode **live**
- [ ] Opencode started in `vibe-demo-app`, model on NAI answers
- [ ] Plan B: a recording of a full run

---

## Troubleshooting

Always start with `scripts/diag.sh`: it shows what the dashboard shows, with links.

| Symptom | Cause / fix |
|---|---|
| Git push: "GitHub API error 401/403" | token wrong or expired, or not scoped to vibe-demo-app |
| GitHub Action: "workflow ci.yml not found" | the app repo was not pushed (step 7) |
| GitHub Action red at "Checkout platform toolkit" | platform repo private or wrong `PLATFORM_REPO` |
| GitHub Action red at "Validate the contract" | open the run: the refused fields are listed |
| GitHub Action red at "Commit deploy/" | branch protection on `main` of vibe-demo-app: remove it |
| Contract accepted stays blue | `GITOPS_SOURCE` is not the Kustomization name (`kubectl -n vibe-demo get kustomization`), or Flux interval |
| Contract accepted red | Flux refused the manifests: the message on the card is Flux's |
| Deployment blue, `ImagePullBackOff` | package still private (step 8) |
| App is ready: "Waiting for a LoadBalancer IP" | no free IP in the MetalLB pool |
| App is ready: "not reachable yet" | the laptop cannot reach the LB IP range (VPN/routing) |
| raz.sh: "tag 'baseline' not found" | the tag was deleted: re-create it on the baseline commit and push it |
| Dashboard red banner | backend exception shown in the banner; `scripts/diag.sh --json` |
