# ShipSage

> From GitHub repo to reviewed DevOps starter kit in minutes.

ShipSage is an AI-assisted DevOps readiness and pipeline generator for teams that need to understand whether a repository is ready for production deployment. Paste a public GitHub repository URL and ShipSage analyzes the stack, scores production readiness, flags blockers, and generates Docker, Kubernetes, CI/CD, Terraform, monitoring, and environment configuration files.

Built for the IBM Bob Hackathon 2026. Powered by IBM watsonx Granite when credentials are provided, with a smart rule-based fallback so the demo still works without API keys.

## The Problem

Small teams often delay deployment because every new repository needs the same painful checklist: container setup, CI/CD, secrets, infrastructure, health checks, monitoring, and cloud configuration. Copy-pasting templates is fast, but risky. One-click deploy promises are attractive, but teams still need to know what is missing before trusting generated infrastructure.

ShipSage helps answer the practical question: "What do I need before this repo can safely move toward production?"

## What ShipSage Does

1. Analyzes a public GitHub repository.
2. Detects language, framework, project type, key files, and repo structure.
3. Scores DevOps readiness using production signals such as tests, CI/CD, Docker, docs, env templates, health checks, and infrastructure code.
4. Shows deployment blockers and next actions.
5. Generates a reviewed starter kit for common deployment assets.

## Generated Assets

| Output | Purpose |
| --- | --- |
| Dockerfile | Multi-stage app container scaffold |
| docker-compose.yml | Local app and detected service orchestration |
| Kubernetes manifests | Deployment, service, ingress, config, secrets, and HPA |
| GitHub Actions pipeline | Build, test, push image, and deploy workflow |
| AWS Terraform | VPC, ECR, EKS, S3, and database scaffolding |
| Monitoring stack | Prometheus, Grafana, Elasticsearch, Logstash, and Kibana |
| Env and Nginx config | Environment template and reverse proxy starter |

## Why This Is Useful

ShipSage is not a blind one-click deployment button. It is a DevOps copilot that gives teams a starting point and tells them what still needs review. That makes it useful for:

- Developers shipping side projects or MVPs
- Student teams preparing hackathon demos
- Startups standardizing deployment basics
- DevOps learners who want to understand production building blocks
- Engineering teams onboarding a new repo

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI |
| Frontend | Vanilla HTML, CSS, JavaScript |
| AI Engine | IBM watsonx Granite with rule-based fallback |
| Repo Analysis | GitHub REST API |
| Generated Targets | Docker, Kubernetes, GitHub Actions, AWS Terraform, ELK, Nginx |

## Getting Started

```bash
git clone https://github.com/AbhishekKharat04/repo-sage.git
cd repo-sage
pip install -r requirements.txt
python main.py
```

Open `http://localhost:8000` and paste a public GitHub repository URL.

## IBM watsonx Credentials

IBM credentials are optional. If you provide an IBM Cloud API key and watsonx Project ID, ShipSage uses Granite for deeper analysis. Without credentials, it still detects stack signals and generates the readiness report using deterministic rules.

## Hackathon Notes

- IBM Bob IDE is the required hackathon component. Export the Bob IDE task session report before submission and place it in `bob_sessions/`.
- IBM watsonx is optional. If you do not have hackathon IBM Cloud access, keep the app on **Rule-based** mode and the core demo still works without billing setup.
- Do not commit IBM Cloud API keys or watsonx credentials. Use environment variables or local-only secrets instead.
- See `HACKATHON_SUBMISSION_CHECKLIST.md` and `DATA_SOURCES.md` before final submission.

## Project Structure

```text
repo-sage/
  main.py              FastAPI server and API routes
  analyzer.py          GitHub repo analyzer, stack detection, readiness scoring
  generators.py        Docker, Kubernetes, CI/CD, Terraform, monitoring generators
  templates/index.html SaaS-style dashboard UI
  requirements.txt
  FEATURES.md
  SETUP.md
```

## Positioning

Existing tools can generate infrastructure snippets. ShipSage focuses on the missing product layer: explaining whether the repo is ready, what is risky, what was generated, and what the user should do next.