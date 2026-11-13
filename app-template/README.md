# vibe-demo-app

The application repo of the **"vibecoded app auto-deployed on NKP"** demo.
It changes at every demo; the platform repo (`__PLATFORM_REPO__`) does not.

```
app/             the web page (written by the AI)          <- AI
contract.yaml    what the app asks from the platform        <- AI + user
deploy/          Kubernetes manifests                       <- platform CI ONLY
.github/         ci.yml calls the platform golden path      <- platform
AGENTS.md        the procedure the AI follows
CONTRACT.md      the contract rules
opencode.json    the commands the AI is allowed to run
```

## Flow

1. The AI writes `app/` and fills `contract.yaml`, then runs the platform's `push.sh`.
2. `ci.yml` calls the platform workflow: validate the contract, build
   `ghcr.io/<owner>/vibe-demo-app:<sha>`, render `deploy/`, commit `deploy: <sha> [skip ci]`.
3. The NKP project `__NAMESPACE__` has a GitOps Source on `./deploy`: Flux applies it.
4. The app is served by a LoadBalancer Service; `/version.txt` returns the commit SHA.

The tag `baseline` is the "Demo on hold" state. `raz.sh` (platform repo) resets
`main` to it. Do not delete or move this tag.

## Running the demo

```bash
cd vibe-demo-app
opencode
```

Then ask for a page, e.g. *"Build a landing page for our Nutanix event in Paris
with a countdown, and deploy it."*
