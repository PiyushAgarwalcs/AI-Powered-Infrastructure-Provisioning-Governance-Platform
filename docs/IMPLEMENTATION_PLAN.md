# AI-Powered Infrastructure Provisioning & Governance Platform
## Implementation & Architecture Plan

**Version:** 1.0.0-draft  
**Date:** November 2026  
**Status:** Step 1 Completed (Repository Audit & Architecture Definition)

---

## 1. Executive Summary & Objective

This project transforms the existing **ShipSage** repository into an **AI-Powered Infrastructure Provisioning & Governance Platform**.

The platform is designed to:
1. Convert natural-language infrastructure requirements into validated, structured specifications using local LLMs (Ollama) and strict Pydantic schemas.
2. Generate production-ready Terraform and Kubernetes configurations without paid APIs or cloud dependencies.
3. Perform deterministic Terraform plan analysis and blast-radius calculation.
4. Enforce strict Open Policy Agent (OPA) / Rego governance policies (e.g. replica limits, exposure controls, forbidden resource destructions).
5. Require explicit, human-in-the-loop approval before any action is permitted.
6. Support controlled local deployment to a Kubernetes cluster (Kind).
7. Maintain an Infrastructure Service Registry tracking provisioned services, configurations, and lifecycle statuses.

---

## 2. Repository Audit & Baseline Architecture

### 2.1 Backend Architecture
- **Framework:** FastAPI (`main.py`) running on Python 3.10+.
- **WebSockets & Real-time:** `websocket_manager.py` provides real-time state synchronization, user presence, and cursor sharing.
- **Session & Storage:** `session_manager.py` with in-memory storage and optional Redis support.
- **AI Integrations:** `ai_providers.py` supports Watsonx, OpenAI, Anthropic, and local Ollama, with a rule-based fallback mechanism.

### 2.2 Generators & Templates
- `generators.py` contains template generation routines:
  - `gen_dockerfile()`: Generates multi-stage Dockerfiles for Python, Node, Go, Java.
  - `gen_compose()`: Generates `docker-compose.yml` for local multi-container development.
  - `gen_kubernetes()`: Generates Kubernetes Deployments, Services, ConfigMaps, Secrets, Ingress, and HPA.
  - `gen_aws_terraform()`: Generates AWS Terraform code (VPC, Subnets, EKS, RDS, ECR, S3).
  - `gen_monitoring()`: Generates Prometheus & Grafana monitoring configurations.
  - `gen_env_and_nginx()`: Generates environment templates and Nginx reverse proxy configurations.

### 2.3 Analysis, Cost & Security Modules
- `analyzer.py`: GitHub repository structural analysis and heuristic readiness scoring.
- `cost_estimator.py` & `cost_optimizer.py`: AWS pricing heuristics and cost optimization suggestions.
- `security_compliance.py`: Scans generated configurations against security benchmarks (CIS, OWASP, SOC2).
- `visualizations.py`: Generates SVG technology radars, confidence meters, and cost charts.
- `exporter.py`: Bundles generated infrastructure artifacts into zip archives.

### 2.4 Frontend Layer
- `templates/index.html`: Responsive single-page application built with modern dark/light CSS, Tailwind-inspired utility classes, Highlight.js for code previews, and Chart.js.
- `templates/collaboration.js`: Client-side WebSocket client for real-time interaction.

---

## 3. Reusable Components & Transition Strategy

| Component | Current Role | Target Platform Role | Action |
| :--- | :--- | :--- | :--- |
| `main.py` | FastAPI entry point & API routes | Main API server for provisioning & governance workflows | **Reuse & Extend** |
| `templates/index.html` | ShipSage repo analysis dashboard | Infrastructure request, plan review, governance & approval UI | **Rebrand & Enhance (Step 2)** |
| `ai_providers.py` | Multi-LLM provider client | Ollama requirement extraction client | **Reuse & Adapt (Step 3)** |
| `generators.py` | Repo-to-code generators | Spec-to-Terraform & Spec-to-Kubernetes generators | **Refactor to consume Pydantic specs (Step 4)** |
| `cost_estimator.py` | AWS cost heuristics | Infrastructure cost estimation preview | **Preserve** |
| `security_compliance.py` | Heuristic security compliance scanner | Secondary security insights alongside OPA | **Preserve & Complement** |
| `session_manager.py` | In-memory session tracking | Base for request tracking & service registry | **Reuse (Step 8)** |
| Legacy hackathon files | Hackathon submission notes (`bob_sessions/`, `PHASE*.md`) | Not relevant to the new platform | **Removed in Step 1** |

---

## 4. Setup Problems & Baseline Issues Identified

1. **Python Syntax Incompatibility in `generators.py`**:
   - *Problem:* Line 298 contained nested backslashes (`\n`) inside an f-string expression: `{"..." if lang == "python" else ...}`. This violates Python syntax rules prior to Python 3.12 (PEP 701) and caused immediate `SyntaxError` on Python 3.10.
   - *Resolution:* Extracted configuration dictionaries outside of the f-string in `generators.py`. All Python modules now compile cleanly under Python 3.10+.
2. **Missing Automated Test Suite**:
   - *Problem:* The original repository contained testing guides (`TESTING_GUIDE.md`) but zero automated unit or integration tests (`pytest` collected 0 items).
   - *Resolution:* Automated unit tests will be systematically introduced starting in Step 3 (spec models and mocked parser) through Step 9.
3. **Repository Licensing**:
   - *Audit finding:* No upstream `LICENSE` file was present in the repository root. A standard open-source license (MIT) is recommended.
4. **Git & Security Configuration**:
   - *Problem:* Default `.gitignore` lacked comprehensive exclusions for Terraform states, plan binaries, and local databases.
   - *Resolution:* `.gitignore` updated to strictly exclude `.env*`, `*.tfstate*`, `*.tfplan`, `*.plan`, `.terraform/`, `*.db`, `*.sqlite`, and secret keys.

---

## 5. Step-by-Step Execution Plan

```
Step 1: Audit, baseline fix, git configuration, and implementation plan [DONE]
Step 2: Rebranding UI and infrastructure request interface
Step 3: AI natural-language requirement parser with Ollama & Pydantic validation
Step 4: Spec-driven Terraform & Kubernetes manifest generator
Step 5: Terraform plan execution, JSON extraction, and blast-radius calculation
Step 6: OPA/Rego governance policies and cryptographic approval workflow
Step 7: Local Kubernetes provisioning on Kind
Step 8: SQLite-backed Infrastructure Service Registry
Step 9: Comprehensive test suite (unit, integration, error paths)
Step 10: Platform documentation, architecture diagrams, and v1.0.0 release
```

---

## 6. Safety & Security Guarantees

- **No Blind Shell Execution:** No model-generated shell commands are ever passed directly to a system shell.
- **Zero Cost Dependencies:** Works entirely with free, local tooling (Ollama, Terraform CLI, Kind, OPA, SQLite).
- **Mandatory Human-in-the-Loop:** Terraform plans and Kubernetes deployments require explicit user authorization before execution.
- **Tamper-Proof Plans:** Applied plans are cryptographically verified against the plan approved during the governance phase.
