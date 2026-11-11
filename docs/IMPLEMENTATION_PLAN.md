# Implementation status and architecture notes

## Project objective

Transform the ShipSage starter code into a local-first infrastructure provisioning and governance workflow: turn infrastructure requirements into a validated specification, generate reviewable configuration, analyze Terraform plans, evaluate deterministic policy rules, require explicit approval, and optionally deploy to a local Kind cluster.

## Actual architecture

- **API and UI:** FastAPI application in `main.py`; vanilla HTML, CSS, and JavaScript in `templates/index.html`.
- **Specification parsing:** Pydantic `InfrastructureSpec` and a parser that supports local Ollama plus a deterministic rule-based fallback (`requirement_parser.py`, `ai_providers.py`).
- **Generation:** Terraform, Kubernetes, Dockerfile, and Compose templates in `generators.py`, checked by `config_validator.py`.
- **Plan analysis:** `terraform_runner.py` parses Terraform plan data and computes a deterministic blast-radius score. CLI mode is optional; the default is mock analysis.
- **Governance:** `governance.py` evaluates deterministic Python rules and manages in-memory approval records. There is no OPA/Rego runtime in this checkout.
- **Local deployment:** `kubernetes_provisioner.py` validates generated manifests and local Kind API context before invoking bounded `kubectl` operations. It requires an approved record and matching validated specification.
- **Service registry:** `service_registry.py` persists registered services to SQLite. Its database is local and ignored by Git.
- **Retained modules:** Repository analysis, cost estimation, collaboration, and related features remain available from the original application; they are outside the core provisioning flow.

See [architecture.md](architecture.md) for the workflow diagram, API sequence, and safety boundaries.

## Delivered implementation

| Step | Scope | Status |
| --- | --- | --- |
| 1 | Repository audit and implementation plan | Complete |
| 2 | Product rebranding and infrastructure request interface | Complete |
| 3 | AI/rule-based requirement parsing and Pydantic validation | Complete |
| 4 | Specification-driven Terraform, Kubernetes, Docker, and Compose generation | Complete |
| 5 | Terraform plan parsing and blast-radius analysis | Complete |
| 6 | Deterministic governance checks and human approval controls | Complete |
| 7 | Controlled deployment to local Kind clusters | Complete |
| 8 | SQLite infrastructure service registry | Complete |
| 9 | Parser resilience and end-to-end workflow tests | Complete |
| 10 | User, setup, architecture, and testing documentation | Complete |

## Safety and operational limits

- Model output is parsed as data; it is not executed as a command.
- Terraform analysis does not run `terraform apply`. CLI mode uses an isolated temporary directory and runs only formatting, initialization without a backend, validation, planning, and plan display.
- Kubernetes deployment targets only a Kind context whose API endpoint is loopback. The target image must already exist in the cluster.
- Policy checks are deterministic Python rules, not OPA/Rego evaluation. A policy failure blocks approval.
- Approval state is process-local; a server restart clears it. The API has no user authentication or authorization and should remain on a trusted local machine.
- Generated manifests and IaC require review and replacement of example credentials before real use.
- Live Kind provisioning was not available in the development environment; the external command paths are covered by mocked tests.

## Repository, attribution, and license

This checkout retains code from the ShipSage/RepoSage project at [AbhishekKharat04/repo-sage](https://github.com/AbhishekKharat04/repo-sage). No `LICENSE` file is present in this checkout. Refer to upstream licensing terms before redistributing or reusing upstream work.
