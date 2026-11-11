# Windows setup

## Application prerequisites

- Windows 10/11 and Python 3.10 or later.
- PowerShell.
- Git.

The rule-based parser, request form, generators, and mock Terraform plan analysis run locally without cloud credentials, Ollama, Docker, Redis, Terraform, or Kind.

## Install and run

From PowerShell:

```powershell
git clone https://github.com/PiyushAgarwalcs/AI-Powered-Infrastructure-Provisioning-Governance-Platform.git
Set-Location 'AI-Powered-Infrastructure-Provisioning-Governance-Platform'
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

If PowerShell blocks activation, use the virtual environment's interpreter directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to loopback on port 8000. Stop it with `Ctrl+C`.

For automated tests, install the development dependencies and run the test suite:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Optional local Ollama parser

1. Install Ollama for Windows from [ollama.com/download/windows](https://ollama.com/download/windows).
2. Start the Ollama application/server and download a model, for example:

   ```powershell
   ollama pull llama3
   ollama list
   ```

3. In the dashboard's AI parse options, select **Ollama (Local)**. The default model is `llama3`, and the default endpoint is `http://localhost:11434`.
4. Enter a requirement and choose **AI Parse & Autofill**. If Ollama is unavailable or returns unusable output, parsing falls back to deterministic rules.

Ollama runs locally and does not require a paid API key. Model downloads require disk space and an internet connection. Rule-based parsing remains available without Ollama.

## Optional Terraform plan execution

Install Terraform CLI from [HashiCorp's Windows instructions](https://developer.hashicorp.com/terraform/install#windows) and ensure `terraform` is on `PATH`. The default analysis mode is a deterministic mock and does not require Terraform.

When `use_cli` is explicitly enabled, the server runs `terraform fmt`, `terraform init -backend=false`, `terraform validate`, `terraform plan`, and `terraform show -json` in a temporary directory. It never runs `terraform apply`; temporary plan files are removed afterward. Provider initialization can require internet access, and Terraform planning can read external provider data. Review the HCL and credentials before requesting CLI mode.

## Optional local Kind deployment

Kind provisioning is separate from Terraform analysis and targets only a loopback Kubernetes API. Install and start [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), then install [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) and [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/). Verify the tools:

```powershell
docker version
kind version
kubectl version --client
```

Create a local cluster and confirm it is available:

```powershell
kind create cluster --name infra-dev
kind get clusters
kubectl --context kind-infra-dev cluster-info
```

Before deploying, build the generated application image and load it into the target Kind cluster. Generated manifests refer to `<service_name>:latest`; for a service named `orders-api`, for example:

```powershell
docker build -t orders-api:latest <generated-application-directory>
kind load docker-image orders-api:latest --name infra-dev
```

The generated application directory must contain the application source expected by its generated Dockerfile. The deployment endpoint verifies the Kind cluster context, generated manifest kinds and namespace, an approved governance record, and an exact specification match. Use the dashboard/API to inspect cluster and workload status.

## Optional settings and local data

- `REDIS_URL` is read at application startup for optional session storage. Redis is not needed for the infrastructure workflow.
- `INFRASTRUCTURE_REGISTRY_DB` can point the service registry at a chosen SQLite database file. By default, the database is `infrastructure_registry.sqlite3` beside the application.
- Ollama model and endpoint are request fields; no `.env` file is needed for local parsing.
- Do not put real API keys, credentials, Terraform state, plan files, or generated secrets in Git. `.gitignore` excludes common local secret/state/database files.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError` | Activate the virtual environment and run `python -m pip install -r requirements.txt` |
| Port 8000 is occupied | Stop the other process using port 8000; the current entry point uses that fixed port |
| Ollama parse falls back to rules | Confirm Ollama is running, the model is present (`ollama list`), and the endpoint is reachable |
| No Kind clusters are listed | Confirm Docker Desktop is running and `kind get clusters` succeeds |
| Kind deployment reports image pull errors | Build the image with the exact `<service_name>:latest` tag and load it into the same Kind cluster |
| Registry file cannot be opened | Check the parent directory permissions or set `INFRASTRUCTURE_REGISTRY_DB` to a writable path |

For API routes, see the interactive [OpenAPI documentation](http://127.0.0.1:8000/docs) while the server is running.
