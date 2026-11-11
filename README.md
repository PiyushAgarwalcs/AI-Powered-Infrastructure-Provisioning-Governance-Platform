# AI-Powered Infrastructure Provisioning & Governance Platform

Turn a natural-language infrastructure request into a validated specification, reviewable Terraform and Kubernetes configuration, and a policy-governed local deployment workflow.

![Redesigned infrastructure request workflow](docs/screenshots/dashboard.png)

> **Safety notice:** This project is a development prototype, not a production provisioning system. Terraform analysis does not apply plans or create cloud resources. Kubernetes deployment is a separate, explicit action limited to a validated local Kind cluster. Run the application only on a trusted local machine.

## What it does

- **Capture requirements:** Submit a natural-language request and infrastructure options through the dashboard or API.
- **Parse and validate:** Use a local Ollama model when available, or deterministic rule-based parsing; validate the result with Pydantic.
- **Generate configuration:** Produce Terraform, Kubernetes, Dockerfile, and Compose artifacts from a validated specification.
- **Review changes:** Validate generated configuration and analyze Terraform plan changes, dependencies, and blast radius. Analysis uses a mock plan by default; Terraform CLI mode is optional.
- **Apply governance:** Evaluate deterministic Python policies and create an approval record that a human must explicitly approve or reject.
- **Provision locally:** Deploy generated Kubernetes manifests only to a validated Kind cluster after approval.
- **Track services:** Keep service and deployment records in a local SQLite registry.

The dashboard's **Generate configuration** action creates files for review; it does not provision infrastructure. Policy evaluation and local Kubernetes deployment are separate workflows.

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend and API | Python, FastAPI, Pydantic |
| Dashboard | HTML, CSS, and vanilla JavaScript |
| Local service registry | SQLite |
| Optional integrations | Ollama, Terraform CLI, Docker, Kind, `kubectl`, Redis |

## Workflow

1. Enter infrastructure requirements in the dashboard or call the parsing API.
2. Review the validated specification and generate configuration artifacts.
3. Inspect the Terraform plan analysis and governance results.
4. Approve or reject the governance record.
5. If desired, separately deploy the approved specification to a local Kind cluster.

## Quick start on Windows

### Requirements

- Windows 10 or 11
- Python 3.10 or later
- PowerShell and Git

The request form, rule-based parser, generators, and mock Terraform analysis work locally. They do not require a cloud account, API key, Ollama, Redis, Terraform, Docker, or Kind.

### Install and run

```powershell
git clone https://github.com/PiyushAgarwalcs/AI-Powered-Infrastructure-Provisioning-Governance-Platform.git
Set-Location 'AI-Powered-Infrastructure-Provisioning-Governance-Platform'
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with `Ctrl+C`.

If PowerShell blocks virtual-environment activation, use its interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Optional integrations

| Integration | Purpose | Required for |
| --- | --- | --- |
| [Ollama](https://ollama.com/) | Local model-assisted requirement parsing | AI-assisted parsing; rule-based parsing works without it |
| [Terraform CLI](https://developer.hashicorp.com/terraform/install) | Optional Terraform format, validation, and plan analysis | CLI plan mode; mock plan analysis is the default |
| [Docker](https://docs.docker.com/desktop/setup/install/windows-install/) and [Kind](https://kind.sigs.k8s.io/) | Local Kubernetes cluster and image workflow | Local Kubernetes deployment |
| `kubectl` | Inspect and manage the local Kind cluster | Local Kubernetes deployment |
| Redis | Optional legacy collaboration/session storage | Collaboration features only |

Integration setup, configuration, and safety details are in the [Windows setup guide](docs/setup.md).

## API

The interactive OpenAPI reference is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) while the application is running. Key endpoint groups:

| Area | Routes |
| --- | --- |
| Health | `GET /health` |
| Requirements and configuration | `POST /api/infrastructure/parse`, `/generate`, `/download` |
| Dashboard request | `POST /api/provision/request` |
| Terraform analysis | `POST /api/terraform/analyze`, `/blast-radius` |
| Governance and approval | `POST /api/governance/evaluate`, `/approve`, `/reject`; `GET /api/governance/approval/{approval_id}` |
| Local Kubernetes | `GET /api/kubernetes/clusters`, `/status`; `POST /api/kubernetes/deploy` |
| Service registry | `GET` and `POST /api/services`; `GET`, `PATCH`, and `DELETE /api/services/{environment}/{service_name}` |

See the [architecture guide](docs/architecture.md) for the request flow, component responsibilities, and implementation boundaries.

## Development and tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The [testing guide](docs/testing.md) describes focused checks and integration-test boundaries.

## Project structure

```text
infra_platform/
  ai/              Model provider adapters
  analysis/         Repository analysis, costs, reporting, and exports
  collaboration/    Sessions, comments, and WebSocket coordination
  infrastructure/  Specifications, generators, validation, plans, governance, Kind, registry
templates/          Dashboard HTML and browser-side code
tests/              Automated tests organized by workflow
docs/               Setup, testing, architecture, and project guides
monitoring/          Monitoring configuration
main.py              FastAPI application and local entry point
```

Start at the [documentation index](docs/README.md) for all project guides.

## Safety and known limitations

- Governance is implemented as deterministic Python rules. OPA is not integrated, and there is no Rego policy bundle.
- Approval records are kept in process memory and are lost when the server restarts. The application has no authentication or authorization; do not expose it to an untrusted network.
- Terraform analysis never runs `terraform apply`. Optional CLI planning can contact Terraform providers, so only use it with configuration and credentials you trust.
- Kind deployment requires Docker, Kind, `kubectl`, an existing local cluster, and the generated application image loaded into that cluster.
- Generated configuration is a starting point, not production-ready infrastructure. Review it and apply your organization's security controls before use.
- Live Kind provisioning has not been verified in the development environment; automated tests mock external commands.
