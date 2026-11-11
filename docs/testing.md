# Testing guide

## Install test dependencies

Use Python 3.10 or later. From the repository root in PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Run tests

Run the complete suite:

```powershell
python -m pytest -q
```

Run an individual workflow area:

```powershell
python -m pytest -q tests/test_requirement_parser.py tests/test_infrastructure_workflow.py
python -m pytest -q tests/test_infrastructure_interface.py
python -m pytest -q tests/test_configuration_generation.py
python -m pytest -q tests/test_terraform_analysis.py
python -m pytest -q tests/test_governance.py
python -m pytest -q tests/test_kubernetes_provisioner.py
python -m pytest -q tests/test_service_registry.py
```

Tests use mocked LLM responses and mocked Terraform/Kubernetes commands where external tools or services would otherwise be needed. They verify parser validation and fallback, generated files, plan parsing and blast radius, governance decisions and stale-plan rejection, local Kind safety checks, registry operations, and a request-to-approval workflow. The suite does not prove a live cloud or Kind deployment works.

## Optional local smoke checks

Start the application:

```powershell
python main.py
```

Then check the health endpoint and OpenAPI page:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Start-Process http://127.0.0.1:8000/docs
```

To try Ollama, start its local server, pull the model selected in the UI (default `llama3`), and use **AI Parse & Autofill**. The rule-based parser is a valid offline smoke-test path.

To test real Terraform CLI mode, install Terraform and use only reviewed HCL. CLI planning can initialize providers and contact external systems; it never applies changes. To test local deployment, install Docker Desktop, Kind, and kubectl, create a disposable Kind cluster, and ensure the generated image is loaded into that cluster before requesting deployment.

## Test reports and safety

- Do not use production credentials or state for tests.
- Do not commit generated plans, Terraform state, local databases, model files, or credentials.
- Human approval records are process-local and are reset when the application restarts.
- The app has no authentication; keep smoke tests bound to loopback and do not expose the server to an untrusted network.
