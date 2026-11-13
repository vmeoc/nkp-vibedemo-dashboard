# The platform contract

The contract (`contract.yaml`) is the agreement between the NKP platform team and
the application team. The application says **what it needs**; the platform decides
**how** it is deployed (Deployment, Service, resources, labels). Nobody writes
Kubernetes YAML by hand: the platform renders `deploy/` from this file.

Format: flat, one `key: value` per line, `#` for comments.

| Field | Type | Required | Values and rules |
|---|---|---|---|
| `app` | string | yes | Application name. Lowercase letters, digits and dashes, 40 characters max. Becomes the name of the Deployment and the Service. **Do not change it once deployed** (a new name = a new app and a new IP address). |
| `owner` | string | yes | Person or team responsible (Kubernetes label: letters, digits, `-`, `_`, `.`; no `@`, no spaces). |
| `cost_center` | string | prod only | Cost center, used for cost reporting. Mandatory in `prod`. |
| `env` | enum | yes | `dev` (Development - relaxed rules, 1 replica by default), `test` (Test - functional acceptance, 1 replica by default), `preprod` (Pre-production - like prod, 2 replicas by default), `prod` (Production - at least 2 replicas, cost center mandatory, no expiry date). |
| `archi` | enum | yes | `stateless` (pods without persistent volume - the only type available today). `backend-db` (backend + new database) and `backend-db-existing` (backend + existing database) are **not supported yet**. |
| `port` | integer | yes | Port the container listens on. The static web template (nginx) listens on **8080**. |
| `replicas` | integer | no | Number of replicas (1-10). Default: 1 in dev/test, 2 in preprod/prod. |
| `size` | enum | yes | `S` Small: requests 0.1 CPU / 128Mi, limits 0.5 CPU / 256Mi. `M` Medium: 0.25 CPU / 256Mi, limits 1 CPU / 512Mi. `L` Large: 0.5 CPU / 512Mi, limits 2 CPU / 1Gi. |
| `protection` | enum | yes | Backup and DR. `none` - Git is enough for a stateless app (RPO = last commit). `daily` - 02:00, 7 days retention (RPO 24h). `hourly` - every hour, 48h retention (RPO 1h). *(Recorded as a label; the backup itself is simulated in this demo.)* |
| `tracing` | boolean | no | `true` = distributed tracing (OpenTelemetry auto-instrumentation injected by the platform, no code change). Default `false`. *(Recorded as a label in this demo.)* |
| `expires` | date | no | Expiry date `YYYY-MM-DD`, set as a label; a platform job deletes the app after that date. **Forbidden in prod.** |

## How to explain the choices to a non-expert user

* **env** - "Is this a test, or something real people will use?" test/demo -> `dev`; real users -> `prod`.
* **size** - "How many visitors at the same time?" a few -> `S`; dozens -> `M`; hundreds -> `L`.
* **protection** - "If the app is lost, is the code in Git enough?" For a static page: yes -> `none`.
* **tracing** - "Do you want to see how each request flows through the app?" yes -> `true`.
* **expires** - "Should the app disappear automatically on a given date?" (not in prod)

## Who checks what

1. `scripts/validate.sh` - on the laptop, before the push (fast feedback).
2. The golden-path workflow - validates again in CI and refuses to render `deploy/` if invalid.
3. Later: admission policies on NKP (Kyverno/Gatekeeper) - the platform itself refuses a non-compliant deployment. The dashboard shows it on "Contract accepted".
