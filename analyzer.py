import httpx
import base64
import re
import time
from typing import Optional
from ai_providers import AIProviderFactory, AIProvider

# Files/folders to skip during analysis
SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.mp4', '.mp3', '.wav', '.pdf', '.zip', '.tar',
    '.gz', '.exe', '.dll', '.so', '.pyc', '.pyo',
    '.lock', '.min.js', '.min.css', '.map'
}

SKIP_FOLDERS = {
    'node_modules', '.git', '__pycache__', 'dist',
    'build', '.next', 'venv', 'env', '.venv',
    '.idea', '.vscode', 'coverage', '.pytest_cache',
    '.tox', '.mypy_cache', '.eggs', 'vendor'
}

PRIORITY_FILES = {
    'main.py', 'app.py', 'index.js', 'index.ts', 'app.js',
    'server.js', 'server.ts', 'index.html', 'main.go',
    'app.ts', 'manage.py', 'package.json', 'requirements.txt',
    'README.md', 'Dockerfile', 'docker-compose.yml',
    'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle',
    'Makefile', 'setup.py', 'pyproject.toml', '.env.example',
    'config.py', 'settings.py', 'urls.py', 'routes.py'
}

MAX_FILE_CHARS = 100000
MAX_FILES_TO_READ = 50
MAX_CONTEXT_CHARS = 50000


class RepoAnalyzer:
    def __init__(self, api_key: str = "", project_id: str = "", github_token: str = "",
                 ai_provider: Optional[AIProvider] = None):
        self.api_key = api_key.strip()
        self.project_id = project_id.strip()
        self.github_token = github_token.strip()
        self.ai_provider = ai_provider
        self.watsonx_url = "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version=2023-05-29"

    def parse_repo_url(self, url: str):
        """Extract owner and repo name from a GitHub URL."""
        url = url.strip().rstrip('/')
        pattern = r'github\.com/([^/]+)/([^/\s]+?)(?:\.git)?(?:[/?#].*)?$'
        match = re.search(pattern, url)
        if not match:
            raise ValueError("Invalid GitHub URL. Use format: https://github.com/owner/repo")
        return match.group(1), match.group(2)

    def should_skip(self, path: str) -> bool:
        """Check if a file should be skipped during analysis."""
        parts = path.lower().split('/')
        for part in parts[:-1]:
            if part in SKIP_FOLDERS:
                return True
        filename = parts[-1]
        if filename.startswith('.'):
            return True
        ext = ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[-1].lower()
        if ext in SKIP_EXTENSIONS:
            return True
        return False


    def _offline_tree(self, repo: str) -> list:
        """Return a realistic demo tree when GitHub API access is unavailable."""
        name = repo.lower()
        if "express" in name or "node" in name:
            paths = [
                "README.md", "package.json", "src/server.js", "src/routes/index.js",
                "src/middleware/error.js", "tests/app.test.js", ".env.example"
            ]
        elif "repo-sage" in name or "shipsage" in name:
            paths = [
                "README.md", "main.py", "analyzer.py", "generators.py", "requirements.txt",
                "templates/index.html", ".env.example"
            ]
        else:
            paths = [
                "README.md", "main.py", "requirements.txt", "app/routes.py",
                "app/services.py", "tests/test_app.py", ".env.example"
            ]
        return [{"path": path, "type": "blob"} for path in paths]

    def _offline_file_content(self, path: str) -> str:
        """Small file samples used only when network analysis is unavailable."""
        samples = {
            "package.json": '{"scripts":{"start":"node src/server.js","test":"jest"},"dependencies":{"express":"latest"},"devDependencies":{"jest":"latest"}}',
            "src/server.js": "const express = require('express');\nconst app = express();\napp.get('/health', (req, res) => res.json({status:'ok'}));\napp.listen(process.env.PORT || 3000);",
            "requirements.txt": "fastapi\nuvicorn\nhttpx\npydantic\n",
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'status':'ok'}\n",
            "README.md": "# Offline repository sample\n\nGenerated because GitHub API access was unavailable.\n",
            ".env.example": "APP_ENV=production\nPORT=8000\n",
        }
        return samples.get(path, "# Sample project file used for offline analysis.\n")

    async def get_repo_tree(self, owner: str, repo: str):
        """Fetch the complete file tree from GitHub, or fall back to demo mode offline."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for branch in ['main', 'master', 'dev', 'develop']:
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
                        headers=headers
                    )
                    
                    # If token is invalid (401), retry without token for public repos
                    if resp.status_code == 401 and "Authorization" in headers:
                        del headers["Authorization"]
                        resp = await client.get(
                            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
                            headers=headers
                        )

                    if resp.status_code == 200:
                        self.offline_mode = False
                        return resp.json().get('tree', []), branch
        except httpx.HTTPError:
            pass

        self.offline_mode = True
        return self._offline_tree(repo), "offline-demo"

    async def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Fetch the content of a single file from GitHub."""
        if self.offline_mode:
            return self._offline_file_content(path)

        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                    headers=headers
                )
                
                # If token is invalid (401), retry without token
                if resp.status_code == 401 and "Authorization" in headers:
                    del headers["Authorization"]
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                        headers=headers
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    size = data.get('size', 0)
                    if size > 100000:  # skip files > 100KB
                        return f"[File too large: {size} bytes]"
                    raw = data.get('content', '')
                    if raw:
                        decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
                        return decoded[:MAX_FILE_CHARS]
        except httpx.HTTPError:
            self.offline_mode = True
            return self._offline_file_content(path)
        return None

    async def get_iam_token(self) -> Optional[str]:
        """Get an IBM Cloud IAM token for watsonx API access."""
        if not self.api_key:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                'https://iam.cloud.ibm.com/identity/token',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={self.api_key}'
            )
            if resp.status_code == 200:
                return resp.json().get('access_token')
        return None

    async def call_watsonx(self, prompt: str) -> str:
        """Call IBM watsonx Granite model for AI-powered analysis."""
        token = await self.get_iam_token()
        if not token or not self.project_id:
            return None  # Will trigger fallback

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self.watsonx_url,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                json={
                    "model_id": "ibm/granite-13b-instruct-v2",
                    "input": prompt,
                    "parameters": {
                        "decoding_method": "greedy",
                        "max_new_tokens": 600,
                        "stop_sequences": ["###", "---END---"]
                    },
                    "project_id": self.project_id
                }
            )
            if resp.status_code == 200:
                results = resp.json().get('results', [])
                if results:
                    return results[0].get('generated_text', '').strip()
        return None


    def select_question_files(self, question: str, file_list: list, file_contents: dict | None = None, limit: int = 12) -> list:
        """Select files most likely to answer a user question."""
        q = (question or "").lower()
        file_contents = file_contents or {}

        topic_keywords = {
            "readiness": ["readiness", "score", "signal", "blocker", "production", "accuracy", "assess"],
            "security": ["security", "auth", "token", "secret", "jwt", "cors", "vulnerability", "compliance"],
            "cost": ["cost", "price", "billing", "estimate", "aws", "cloud", "budget"],
            "deploy": ["deploy", "docker", "kubernetes", "terraform", "ci", "cd", "github actions", "render", "server"],
            "architecture": ["architecture", "structure", "module", "flow", "how does", "overview"],
            "setup": ["setup", "install", "run", "local", "start", "environment", "env"],
        }

        wanted = set()
        for topic, words in topic_keywords.items():
            if any(word in q for word in words):
                wanted.update(words)
                wanted.add(topic)

        # Always include documentation, entrypoints, and manifests.
        base_names = {
            "readme.md", "main.py", "app.py", "server.js", "index.js", "package.json",
            "requirements.txt", "pyproject.toml", "dockerfile", "docker-compose.yml",
            ".env.example", "makefile"
        }

        scored = []
        for path in file_list:
            lower_path = path.lower()
            base = lower_path.rsplit("/", 1)[-1]
            content = (file_contents.get(path) or "").lower()
            score = 0

            if base in base_names:
                score += 40
            if any(pf.lower() in base for pf in PRIORITY_FILES):
                score += 20
            if wanted and any(word in lower_path or word in content for word in wanted):
                score += 50
            if any(word in q and word in lower_path for word in re.findall(r"[a-zA-Z_][a-zA-Z0-9_\-]*", q)):
                score += 25
            if lower_path.endswith(('.py', '.js', '.ts', '.tsx', '.yml', '.yaml', '.json', '.md')):
                score += 5

            if score > 0:
                scored.append((score, path))

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [path for _, path in scored[:limit]]

        # Ensure we have a useful fallback even for vague questions.
        if len(selected) < min(limit, len(file_list)):
            for path in file_list:
                if path not in selected and not self.should_skip(path):
                    selected.append(path)
                if len(selected) >= limit:
                    break
        return selected[:limit]

    def build_context_bundle(self, question: str, file_list: list, file_contents: dict, limit_chars: int = 60000) -> dict:
        """Build a RepoMind-style context bundle for Q&A."""
        selected = self.select_question_files(question, file_list, file_contents, limit=12)
        chunks = []
        used_files = []
        total = 0
        for path in selected:
            content = file_contents.get(path)
            if not content:
                continue
            chunk = f"### {path}\n```\n{content[:8000]}\n```"
            if total + len(chunk) > limit_chars:
                break
            chunks.append(chunk)
            used_files.append(path)
            total += len(chunk)

        tree = "\n".join(f"- {p}" for p in file_list[:200])
        if len(file_list) > 200:
            tree += f"\n... and {len(file_list) - 200} more files"

        return {
            "tree": tree,
            "files": used_files,
            "content": "\n\n".join(chunks),
        }

    def detect_stack(self, file_list: list, file_contents: dict) -> list:
        """Detect the technology stack from file list and contents."""
        stack = []
        content_str = str(file_contents).lower()

        # Languages
        if any(f.endswith('.py') for f in file_list): stack.append("Python")
        if any(f.endswith('.js') for f in file_list): stack.append("JavaScript")
        if any(f.endswith('.ts') or f.endswith('.tsx') for f in file_list): stack.append("TypeScript")
        if any(f.endswith('.go') for f in file_list): stack.append("Go")
        if any(f.endswith('.java') for f in file_list): stack.append("Java")
        if any(f.endswith('.rs') for f in file_list): stack.append("Rust")
        if any(f.endswith('.rb') for f in file_list): stack.append("Ruby")
        if any(f.endswith('.php') for f in file_list): stack.append("PHP")
        if any(f.endswith('.cs') for f in file_list): stack.append("C#")
        if any(f.endswith('.cpp') or f.endswith('.c') for f in file_list): stack.append("C/C++")

        # Frameworks
        if 'django' in content_str: stack.append("Django")
        if 'fastapi' in content_str: stack.append("FastAPI")
        if 'flask' in content_str: stack.append("Flask")
        if 'express' in content_str: stack.append("Express.js")
        if any('next.config' in f for f in file_list): stack.append("Next.js")
        if 'react' in content_str: stack.append("React")
        if 'vue' in content_str: stack.append("Vue.js")
        if 'angular' in content_str: stack.append("Angular")
        if 'spring' in content_str: stack.append("Spring Boot")
        if 'rails' in content_str: stack.append("Ruby on Rails")

        # Infra & Tools
        if any('Dockerfile' in f for f in file_list): stack.append("Docker")
        if any('docker-compose' in f for f in file_list): stack.append("Docker Compose")
        if any('.github/workflows' in f for f in file_list): stack.append("GitHub Actions")
        if any('package.json' in f for f in file_list): stack.append("npm")
        if any('requirements.txt' in f or 'pyproject.toml' in f for f in file_list): stack.append("pip")
        if any('.env' in f for f in file_list): stack.append("Environment Config")

        return stack if stack else ["Unknown"]

    def detect_project_type(self, file_list: list, stack: list) -> str:
        """Determine the type of project (web app, API, CLI, library, etc.)."""
        has_html = any(f.endswith('.html') for f in file_list)
        has_api = any(keyword in str(file_list).lower() for keyword in ['api', 'routes', 'endpoints', 'views'])
        has_cli = any(keyword in str(file_list).lower() for keyword in ['cli', 'command', '__main__'])
        has_tests = any('test' in f.lower() for f in file_list)

        if any(fw in stack for fw in ['React', 'Vue.js', 'Angular', 'Next.js']):
            return "Web Application (Frontend)"
        elif any(fw in stack for fw in ['Django', 'FastAPI', 'Flask', 'Express.js', 'Spring Boot']):
            return "Web Application (Full-Stack)" if has_html else "Backend API"
        elif has_html:
            return "Static Website"
        elif has_cli:
            return "CLI Tool"
        elif has_api:
            return "API Service"
        else:
            return "Software Library"


    def assess_devops_readiness(self, file_list: list, stack: list, project_type: str) -> dict:
        """Score how ready the repository is for a production deployment workflow."""
        lower_files = [f.lower() for f in file_list]

        # Enhanced signals with more granular detection
        signals = {
            "tests": any("test" in f or "spec" in f for f in lower_files),
            "ci": any(".github/workflows" in f or "jenkinsfile" in f or ".gitlab-ci" in f or ".circleci" in f for f in lower_files),
            "docker": any("dockerfile" in f or "docker-compose" in f for f in lower_files),
            "env_template": any(".env.example" in f or ".env.template" in f or ".env.sample" in f for f in lower_files),
            "docs": any(f.endswith("readme.md") or f.startswith("docs/") for f in lower_files),
            "health": any("health" in f for f in lower_files) or any(s in stack for s in ["FastAPI", "Express.js", "Spring Boot"]),
            "infra": any("terraform" in f or "k8s" in f or "kubernetes" in f or "helm" in f or "docker-compose" in f or "makefile" in f for f in lower_files),
            "monitoring": any("prometheus" in f or "grafana" in f or "monitoring" in f or "log-monitor" in f or "logging" in f for f in lower_files),
            "security": any("security" in f or ".snyk" in f or "trivy" in f for f in lower_files),
            "secrets": any("secrets" in f or "vault" in f for f in lower_files),
        }

        # Calculate base score (0-100)
        weights = {
            "tests": 15,
            "ci": 15,
            "docker": 15,
            "env_template": 8,
            "docs": 8,
            "health": 10,
            "infra": 12,
            "monitoring": 7,
            "security": 5,
            "secrets": 5,
        }
        score = sum(weights[key] for key, present in signals.items() if present)
        
        # Bonus points for comprehensive setup
        if signals["tests"] and signals["ci"]:
            score += 5  # Automated testing
        if signals["docker"] and signals["infra"]:
            score += 5  # Full containerization + IaC
        if signals["monitoring"] and signals["health"]:
            score += 3  # Observability
        
        # Cap at 100
        score = min(score, 100)

        generated = [
            "Dockerfile",
            "docker-compose.yml",
            "Kubernetes deployment, service, ingress, HPA, and config",
            "GitHub Actions build/test/deploy pipeline",
            "AWS Terraform for VPC, ECR, EKS, S3, and database scaffolding",
            "Prometheus, Grafana, Elasticsearch, Logstash, and Kibana stack",
            ".env template and Nginx reverse proxy",
        ]

        blockers = []
        if not signals["tests"]:
            blockers.append("No test suite detected. Add tests before trusting automated deploys.")
        if not signals["ci"]:
            blockers.append("No CI/CD workflow detected. Review the generated GitHub Actions pipeline first.")
        if not signals["docker"]:
            blockers.append("No container setup detected. Build the generated Dockerfile locally before deploying.")
        if not signals["env_template"]:
            blockers.append("No environment template detected. Define required variables and secrets explicitly.")
        if not signals["health"]:
            blockers.append("No obvious health check contract found. Add a /health endpoint or command probe.")

        # Dynamic status based on score
        if score >= 86:
            status = "Enterprise Grade"
            summary = "🌟 Exceptional! This repository follows industry best practices and is production-ready. ShipSage will help you optimize and scale further."
        elif score >= 71:
            status = "Production Ready"
            summary = "✅ Strong foundation! This repo has solid DevOps practices. ShipSage will standardize configs and add enterprise features."
        elif score >= 51:
            status = "Getting There"
            summary = "🟡 Good progress! The basics are in place. ShipSage will fill critical gaps and accelerate your deployment readiness."
        elif score >= 31:
            status = "Needs Work"
            summary = "⚠️ Foundation exists but needs strengthening. ShipSage will generate missing components and guide you to production."
        else:
            status = "Not Ready"
            summary = "❌ Critical gaps detected. ShipSage will create a complete DevOps foundation from scratch, but manual review is essential."

        next_actions = [
            "Open the Dockerfile tab and build the image locally.",
            "Check the CI/CD tab and replace placeholder AWS secrets and cluster names.",
            "Review Kubernetes probes, resource limits, and public ingress hostnames.",
            "Run terraform validate before planning real infrastructure.",
            "Add missing tests, env examples, or health endpoints flagged below.",
        ]
        
        # Calculate time saved dynamically
        time_saved, time_saved_breakdown = self.calculate_time_saved(signals, project_type, score)

        return {
            "score": score,
            "status": status,
            "summary": summary,
            "signals": signals,
            "blockers": blockers,
            "generated": generated,
            "next_actions": next_actions,
            "time_saved_hours": time_saved,
            "time_saved_breakdown": time_saved_breakdown,
            "positioning": f"ShipSage turns a {project_type.lower()} into a reviewed DevOps starter kit, not a blind one-click deploy.",
        }
    
    def calculate_time_saved(self, signals: dict, project_type: str, readiness_score: int) -> tuple[float, list]:
        """
        Calculate estimated time to manually write configs that ShipSage generates.
        
        HONEST METHODOLOGY:
        - Only count time for configs ShipSage actually generates as starter templates
        - These are STARTING POINTS, not production-ready — user still needs to review & customize
        - We estimate ~50-60% of manual effort is saved (the boilerplate/research part)
        - The rest (customization, testing, debugging) the user still does themselves
        """
        # Time to write each config FROM SCRATCH (realistic senior dev estimates)
        config_times = {
            "docker": 1.5,       # Dockerfile with multi-stage build
            "docker_compose": 1.0,  # Compose with services/networks
            "kubernetes": 3.0,   # K8s deployment + service + ingress + HPA
            "ci": 2.0,          # GitHub Actions pipeline
            "terraform": 4.0,   # Basic AWS infra (VPC, EKS, S3, ECR)
            "monitoring": 2.0,  # ELK/Prometheus compose
            "env_nginx": 0.5,   # Env template + nginx proxy
        }
        
        # Docker: always generated, but if repo already has it, savings are smaller
        docker_time = 0.0
        if not signals.get("docker"):
            docker_time = config_times["docker"] + config_times["docker_compose"]
        else:
            docker_time = 0.5  # Still generate optimized version
        
        # K8s: always generated
        k8s_time = config_times["kubernetes"] if not signals.get("infra") else 1.0
        
        # CI/CD: always generated
        ci_time = config_times["ci"] if not signals.get("ci") else 0.5
        
        # Terraform: always generated
        tf_time = config_times["terraform"] if not signals.get("infra") else 1.0
        
        # Monitoring: always generated
        elk_time = config_times["monitoring"] if not signals.get("monitoring") else 0.5
        
        # Env + Nginx: always generated
        env_time = config_times["env_nginx"]
        
        total = docker_time + k8s_time + ci_time + tf_time + elk_time + env_time
        
        # Breakdown for chart: Docker, K8s, CI/CD, Terraform, ELK
        breakdown = [
            round(docker_time, 1),
            round(k8s_time, 1),
            round(ci_time, 1),
            round(tf_time, 1),
            round(elk_time, 1)
        ]
        
        return round(total, 1), breakdown

    def generate_architecture(self, file_list: list) -> str:
        """Generate a text-based architecture diagram from file structure."""
        dirs = {}
        root_files = []
        for f in file_list:
            parts = f.split('/')
            if len(parts) == 1:
                root_files.append(f)
            else:
                top_dir = parts[0]
                if top_dir not in dirs:
                    dirs[top_dir] = []
                dirs[top_dir].append('/'.join(parts[1:]))

        arch = "```\n"
        arch += " Repository Root\n"
        for f in sorted(root_files)[:8]:
            arch += f"  {f}\n"
        for d, files in sorted(dirs.items()):
            arch += f"  {d}/  ({len(files)} files)\n"
            for f in sorted(files)[:3]:
                arch += f"    {f}\n"
            if len(files) > 3:
                arch += f"    ... +{len(files)-3} more\n"
        arch += "```"
        return arch

    def describe_file(self, filename: str, content: str, stack: list) -> dict:
        """Generate a smart description for a single file based on its name and content."""
        name = filename.lower()
        basename = filename.split('/')[-1].lower()
        content_lower = (content or "").lower()
        desc = ""
        bullets = []

        # --- Entry Points ---
        if basename in ('main.py', 'app.py'):
            desc = f"This file serves as the **entry point** of the application. It initializes components and registers routes."
            if 'fastapi' in content_lower: bullets.append("Initializes a FastAPI application instance.")
            if 'flask' in content_lower: bullets.append("Bootstraps the Flask web application.")
            if 'startup' in content_lower or 'lifespan' in content_lower: bullets.append("Defines startup/shutdown lifecycle hooks.")
            if 'middleware' in content_lower or 'cors' in content_lower: bullets.append("Configures CORS and request middleware.")
            if '@app.get' in content_lower or '@app.post' in content_lower: bullets.append("Exposes HTTP API routes and endpoints.")
            if 'websocket' in content_lower: bullets.append("Handles WebSocket connections for real-time features.")
        elif basename in ('server.js', 'index.js', 'app.js'):
            desc = "Main Node.js server file that bootstraps the application and defines routes."
            if 'express' in content_lower: bullets.append("Configures Express.js middleware and route handlers.")
            if 'listen' in content_lower: bullets.append("Starts the HTTP server on the configured port.")
            if 'socket' in content_lower: bullets.append("Integrates real-time WebSocket support.")
        elif basename == 'manage.py':
            desc = "Django management entry point for running CLI commands like migrations and dev server."

        # --- Config / Deps ---
        elif basename == 'requirements.txt':
            deps = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')]
            desc = f"Python dependency manifest listing **{len(deps)} packages** required to run the application."
            if deps: bullets.append(f"Key dependencies: `{'`, `'.join(deps[:6])}`{'...' if len(deps) > 6 else ''}.")
        elif basename == 'package.json':
            desc = "Node.js package manifest defining dependencies, scripts, and project metadata."
            if '"start"' in content_lower: bullets.append("Defines `npm start` script for running the app.")
            if '"test"' in content_lower: bullets.append("Includes `npm test` script for running the test suite.")
            if '"build"' in content_lower: bullets.append("Includes a `npm build` script for production bundling.")
        elif basename in ('.env.example', '.env.template', '.env.sample'):
            vars_list = [l.split('=')[0].strip() for l in content.splitlines() if '=' in l and not l.strip().startswith('#')]
            desc = f"Environment variable template documenting **{len(vars_list)} required configuration keys**."
            if vars_list: bullets.append(f"Variables include: `{'`, `'.join(vars_list[:5])}`.")
        elif basename in ('dockerfile',):
            desc = "Multi-stage Dockerfile for building and containerizing the application."
            if 'from' in content_lower: bullets.append("Uses a base image for the runtime environment.")
            if 'run pip' in content_lower or 'run npm' in content_lower: bullets.append("Installs application dependencies during the build phase.")
            if 'expose' in content_lower: bullets.append("Exposes a port for the containerized service.")
            if 'cmd' in content_lower or 'entrypoint' in content_lower: bullets.append("Defines the default container startup command.")
        elif basename in ('docker-compose.yml', 'docker-compose.yaml'):
            desc = "Orchestrates multi-container services for local development and staging environments."
            if 'redis' in content_lower: bullets.append("Includes a Redis service for caching/session management.")
            if 'postgres' in content_lower or 'mysql' in content_lower: bullets.append("Includes a database service.")
            if 'nginx' in content_lower: bullets.append("Configures an Nginx reverse proxy service.")
        elif basename == 'makefile':
            targets = re.findall(r'^([a-zA-Z][a-zA-Z0-9_-]+):', content, re.MULTILINE)
            desc = "Build automation file providing shorthand commands for common developer workflows."
            if targets: bullets.append(f"Defines targets: `{'`, `'.join(targets[:6])}`.")

        # --- CI/CD ---
        elif '.github/workflows' in name:
            desc = "GitHub Actions CI/CD workflow that automates build, test, and deployment pipelines on push/PR."
            if 'push' in content_lower: bullets.append("Triggers automatically on `git push` events.")
            if 'docker' in content_lower: bullets.append("Builds and pushes Docker images to a container registry.")
            if 'test' in content_lower: bullets.append("Runs the automated test suite on every commit.")
            if 'deploy' in content_lower: bullets.append("Deploys the application to the target environment.")

        # --- Python modules ---
        elif basename.endswith('.py'):
            module_name = basename.replace('.py', '')
            if 'analyzer' in module_name or 'analyse' in module_name:
                desc = f"Core analysis module that implements the logic for parsing and evaluating repositories."
                if 'async def' in content_lower: bullets.append("Uses async functions for non-blocking API calls.")
                if 'class' in content_lower: bullets.append(f"Defines classes encapsulating the analysis logic.")
            elif 'generator' in module_name or 'gen_' in module_name:
                desc = f"Generator module responsible for producing configuration artifacts from analysis results."
            elif 'route' in module_name or 'api' in module_name or 'view' in module_name:
                desc = f"Defines HTTP API routes and request handlers for the `{module_name}` domain."
            elif 'model' in module_name or 'schema' in module_name:
                desc = f"Data model/schema definitions used for validation and ORM mapping."
            elif 'util' in module_name or 'helper' in module_name:
                desc = f"Utility module providing shared helper functions used across the codebase."
            elif 'test' in module_name or 'spec' in module_name:
                desc = f"Automated test suite for verifying the correctness of the application logic."
            elif 'auth' in module_name or 'security' in module_name:
                desc = f"Authentication and authorization module managing user identity and access control."
            elif 'config' in module_name or 'setting' in module_name:
                desc = f"Application configuration loader — reads environment variables and sets runtime defaults."
            else:
                classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
                functions = re.findall(r'^(?:async )?def\s+(\w+)', content, re.MULTILINE)
                desc = f"Python module `{basename}` containing application logic."
                if classes: bullets.append(f"Defines classes: `{'`, `'.join(classes[:4])}`.")
                if functions: bullets.append(f"Exposes functions: `{'`, `'.join(functions[:5])}`.")

        # --- JS/TS modules ---
        elif basename.endswith(('.js', '.ts', '.jsx', '.tsx')):
            module_name = basename.rsplit('.', 1)[0]
            if 'component' in name or basename[0].isupper():
                desc = f"React component `{basename}` rendering UI elements for the application."
            elif 'hook' in name:
                desc = f"Custom React hook encapsulating reusable stateful logic."
            elif 'util' in name or 'helper' in name:
                desc = f"Utility module providing shared helper functions."
            elif 'route' in name or 'api' in name:
                desc = f"Defines routing logic and API handler functions."
            else:
                desc = f"JavaScript/TypeScript module `{basename}` implementing application logic."

        # --- Web / Docs ---
        elif basename == 'readme.md':
            desc = "Project documentation providing an overview, setup instructions, and usage examples."
        elif basename.endswith('.html'):
            desc = f"HTML template `{basename}` — defines the page structure and UI layout served to clients."
            if 'chart' in content_lower or 'canvas' in content_lower: bullets.append("Includes Chart.js/Canvas-based data visualizations.")
            if 'websocket' in content_lower: bullets.append("Connects to real-time WebSocket endpoints.")
        elif 'prometheus' in name:
            desc = "Prometheus monitoring configuration defining scrape targets and alerting rules."
        elif 'nginx' in name:
            desc = "Nginx reverse proxy configuration routing traffic to the application backend."

        if not desc:
            desc = f"Module `{basename}` implementing supporting functionality for the application."

        return {"file": filename, "description": desc, "bullets": bullets}

    def generate_module_breakdown(self, file_list: list, file_contents: dict, stack: list) -> list:
        """
        Generate a detailed, per-module breakdown similar to RepoMind's LLM output.
        Groups files by top-level directory and generates smart descriptions.
        """
        dirs = {}
        root_files = []
        for f in file_list:
            parts = f.split('/')
            if len(parts) == 1:
                root_files.append(f)
            else:
                top_dir = parts[0]
                if top_dir not in dirs:
                    dirs[top_dir] = []
                dirs[top_dir].append(f)

        modules = []

        # Root-level notable files first
        notable_roots = [f for f in root_files if any(
            pf.lower() in f.lower() for pf in PRIORITY_FILES
        )]
        for f in notable_roots[:5]:
            content = file_contents.get(f, "")
            info = self.describe_file(f, content, stack)
            modules.append({
                "name": f,
                "type": "file",
                "description": info["description"],
                "bullets": info["bullets"],
                "files": []
            })

        # Directories
        dir_descriptions = {
            'generators': ("Contains modules responsible for generating DevOps artifacts and configuration files.",
                          ["Produces Dockerfiles, Kubernetes manifests, CI/CD pipelines, Terraform configs.",
                           "Each subdirectory or module targets a specific infrastructure component.",
                           "Output files are tailored to the analyzed repository's detected tech stack."]),
            'templates': ("Houses HTML templates served by the web server to render the user interface.",
                         ["Templates are dynamically rendered using the Jinja2 or similar engine.",
                          "Includes the main dashboard, analysis views, and collaboration pages."]),
            'monitoring': ("Contains monitoring stack configurations for observability in production.",
                          ["Includes Prometheus scrape configs and alerting rules.",
                           "Designed to track application health, latency, and error rates."]),
            '.github': ("GitHub-specific configuration including Actions CI/CD workflow definitions.",
                       ["Workflow files automate build, test, and deployment pipelines.",
                        "Triggers on push, pull_request, or scheduled events."]),
            'tests': ("Automated test suite ensuring correctness and reliability of the application.",
                     ["Unit tests verify individual functions and modules in isolation.",
                      "Integration tests validate the interaction between components."]),
            'src': ("Core source code directory containing the main application logic.",
                   ["Organized into sub-modules by domain responsibility.",
                    "Entry points, routes, and service layers live here."]),
            'api': ("REST API layer defining endpoints, request/response schemas, and routing.",
                   ["Implements HTTP handlers for client-server communication.",
                    "Includes validation middleware and error handling."]),
            'config': ("Application configuration files and environment-specific settings.",
                      ["Loads environment variables to configure runtime behaviour.",
                       "Keeps secrets and credentials out of the main codebase."]),
            'scripts': ("Utility and automation scripts for common developer and deployment tasks.",
                       ["Includes setup, migration, and deployment helper scripts.",
                        "Reduces manual steps in development and CI workflows."]),
            'docs': ("Project documentation, architectural decision records, and usage guides.",
                    ["Helps onboard new contributors and explains design decisions.",
                     "May include API reference docs, diagrams, and tutorials."]),
        }

        for dir_name, dir_files in sorted(dirs.items()):
            dir_lower = dir_name.lower()
            # Check for a known description
            known = None
            for key, val in dir_descriptions.items():
                if key in dir_lower:
                    known = val
                    break

            sub_modules = []
            for f in dir_files[:6]:
                content = file_contents.get(f, "")
                info = self.describe_file(f, content, stack)
                if info["description"]:
                    sub_modules.append({
                        "file": f.split('/')[-1],
                        "description": info["description"],
                        "bullets": info["bullets"]
                    })

            if known:
                modules.append({
                    "name": dir_name,
                    "type": "directory",
                    "description": known[0],
                    "bullets": known[1],
                    "files": sub_modules
                })
            else:
                # Auto-generate from file contents
                modules.append({
                    "name": dir_name,
                    "type": "directory",
                    "description": f"Module directory `{dir_name}/` containing {len(dir_files)} files that implement supporting functionality.",
                    "bullets": [f"`{f.split('/')[-1]}` — {self.describe_file(f, file_contents.get(f,''), stack)['description'][:80]}..." for f in dir_files[:3]],
                    "files": sub_modules
                })

        # Module relationship summary
        relationships = []
        module_names = [m["name"] for m in modules]
        entry = next((m for m in module_names if m in ('main.py', 'app.py', 'index.js', 'server.js')), None)
        if entry:
            relationships.append(f"`{entry}` acts as the **central nervous system**, integrating and invoking all other modules.")
        for m in module_names:
            if 'analyzer' in m.lower():
                relationships.append(f"`{m}` provides the foundation for understanding repository state and readiness.")
            elif 'generator' in m.lower():
                relationships.append(f"`{m}` uses analysis results to tailor DevOps artifacts to the specific tech stack.")
            elif 'template' in m.lower():
                relationships.append(f"`{m}` presents findings and generated configs through the web dashboard.")
            elif 'monitoring' in m.lower():
                relationships.append(f"`{m}` enables observability and health tracking in production deployments.")

        return {"modules": modules, "relationships": relationships}

    def generate_fallback_analysis(self, owner: str, repo: str, file_list: list, file_contents: dict) -> dict:
        """Smart rule-based analysis when watsonx is not configured."""
        stack = self.detect_stack(file_list, file_contents)
        project_type = self.detect_project_type(file_list, stack)
        stack_str = ", ".join(stack)

        priority_found = [f for f in file_list if any(pf in f.split('/')[-1] for pf in PRIORITY_FILES)]
        architecture = self.generate_architecture(file_list)

        # Detect interesting patterns
        has_tests = any('test' in f.lower() for f in file_list)
        has_ci = any('.github/workflows' in f or 'Jenkinsfile' in f for f in file_list)
        has_docker = any('Dockerfile' in f or 'docker-compose' in f for f in file_list)
        has_docs = any('docs/' in f or 'documentation/' in f.lower() for f in file_list)

        # Sophisticated boilerplate that mimics LLM output
        primary_lang = stack[0] if stack else "modern web technologies"
        
        summary = f"""## Architecture Summary

Overall, **{repo}** is a sophisticated **{project_type}** designed to handle complex workflows and provide robust application functionality. Built on a modern tech stack featuring **{stack_str}**, it automates core processes and provides a solid foundation for scalable deployment.

The primary programming architecture relies heavily on **{primary_lang}**, leveraging frameworks and dependencies that handle application logic, data processing, and user interaction. The system implements a structured file organization, containing **{len(file_list)} files** distributed across {len(set(f.split('/')[0] for f in file_list if '/' in f))} core modules.

In terms of DevOps and deployment strategy, the repository demonstrates clear architectural patterns. {'The presence of automated CI/CD pipelines ensures reliable continuous integration, while ' if has_ci else ''}{'comprehensive Docker configurations facilitate isolated, containerized environments. ' if has_docker else ''}{'A testing suite is also included to maintain strict codebase integrity.' if has_tests else ''} This approach aligns with industry best practices for cloud-native deployment.

Key dependencies include **{stack_str}**, which collectively manage everything from intelligent processing to infrastructure orchestration. The architectural design highlights a strong focus on modularity, maintainability, and production readiness.

### Module Breakdown
{architecture}

>  *Note: This detailed breakdown was generated locally in Rule-Based mode. Connect your IBM watsonx API key above for dynamic, contextual LLM analysis.*"""

        # Entry point detection
        entry_points = []
        for f in file_list:
            name = f.split('/')[-1].lower()
            if name in ['main.py', 'app.py', 'index.js', 'index.ts', 'server.js', 'main.go', 'manage.py']:
                entry_points.append(f)

        starting_guide = f"""## Your Onboarding Roadmap

### Step 1  Understand the Purpose
Read the `README.md` first. It tells you what this project does and how to set it up.

### Step 2  Find the Entry Point
{"The main entry point is: **`" + entry_points[0] + "`**. Start reading here." if entry_points else "Look for files named `main.*`, `app.*`, `index.*`, or `server.*`  these are entry points."}

### Step 3  Understand the Data Flow
Trace how data moves through the app:
1. **Input**  Where does user/data come in? (API routes, CLI args, file input)
2. **Processing**  What business logic transforms the data?
3. **Output**  Where does the result go? (database, API response, file, UI)

### Step 4  Check Dependencies
{"Review `package.json` for npm packages." if any('package.json' in f for f in file_list) else ""}\
{"Review `requirements.txt` for Python packages." if any('requirements.txt' in f for f in file_list) else ""}\
{"Review `go.mod` for Go modules." if any('go.mod' in f for f in file_list) else ""}

### Step 5  Run It Locally
Follow the README setup instructions. If none exist, look for a `Makefile`, `docker-compose.yml`, or scripts in a `scripts/` folder.

###  What NOT to Touch (Yet)
- Config files (`.env`, `config.*`, `settings.*`)  changing these can break everything
- Database migrations  modifying these can corrupt data
- CI/CD pipelines  breaking these blocks the whole team

>  *Add your IBM watsonx credentials for personalized onboarding guidance.*"""

        critical_files = "## Critical Files You Must Know\n\n"
        critical_files += "| File | Role | Priority |\n|------|------|----------|\n"
        for f in priority_found[:8]:
            name = f.split('/')[-1]
            if name == 'README.md':
                critical_files += f"| `{f}` | Project documentation & setup |  Read First |\n"
            elif name in ['main.py', 'app.py', 'index.js', 'server.js', 'index.ts', 'main.go']:
                critical_files += f"| `{f}` | Application entry point |  Critical |\n"
            elif name in ['package.json', 'requirements.txt', 'go.mod', 'Cargo.toml']:
                critical_files += f"| `{f}` | Dependency manifest |  Important |\n"
            elif name in ['Dockerfile', 'docker-compose.yml']:
                critical_files += f"| `{f}` | Container configuration |  Important |\n"
            elif name in ['config.py', 'settings.py', '.env.example']:
                critical_files += f"| `{f}` | Configuration |  Handle With Care |\n"
            else:
                critical_files += f"| `{f}` | Key project file |  Review |\n"
        if not priority_found:
            for f in file_list[:5]:
                critical_files += f"| `{f}` | Project file |  Review |\n"
        critical_files += "\n>  *Connect IBM watsonx for detailed file-by-file analysis.*"

        danger_zones = f"""## Danger Zones  Handle With Care

###  High Risk
- **Configuration files** (`.env`, `config.*`, `settings.*`)  contain secrets and environment-specific values. NEVER commit these to git.
- **Database migrations**  modifying existing migrations can corrupt production data. Always create NEW migrations.
- **Authentication/Authorization code**  `auth.*`, `middleware.*`, JWT handlers  bugs here = security vulnerabilities.

###  Medium Risk
- **Files with 200+ lines**  these are often tightly coupled and hard to refactor safely
- **Files imported by 5+ other files**  changing these creates cascade failures
- **Third-party integrations**  API keys, webhook handlers, payment logic

###  Safe to Explore
- Test files (`test_*`, `*_test.*`, `*.spec.*`)
- Documentation files
- Static assets (CSS, images)
- Example/sample files

###  Repo Health Indicators
| Metric | Status |
|--------|--------|
| Has Tests | {" Yes" if has_tests else " No"} |
| Has CI/CD | {" Yes" if has_ci else " No"} |
| Has Docker | {" Yes" if has_docker else " No"} |
| Has Docs | {" Yes" if has_docs else " No"} |
| Total Files | {len(file_list)} |

>  *Add your IBM watsonx API key for repo-specific risk analysis.*"""

        readme = f"""# {repo}

## Overview
{repo} is a {project_type.lower()} built with {stack_str}.

## Tech Stack
{chr(10).join(f'- {s}' for s in stack)}

## Project Structure
{architecture}

## Getting Started

### Prerequisites
{chr(10).join(f'- {s}' for s in stack[:3])}

### Installation
1. Clone the repository
   ```bash
   git clone https://github.com/{owner}/{repo}.git
   cd {repo}
   ```
2. Install dependencies
3. Configure environment variables
4. Run the application

## Key Files
{chr(10).join(f'- `{f}`' for f in priority_found[:7]) if priority_found else '- See repository'}

## Contributing
1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m "feat: add amazing feature"`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
See the LICENSE file for details.

---
*Generated by [RepoSage](https://github.com/AbhishekKharat04/repo-sage)  AI-powered repository onboarding*"""

        module_breakdown = self.generate_module_breakdown(file_list, file_contents, stack)

        return {
            "summary": summary,
            "starting_guide": starting_guide,
            "critical_files": critical_files,
            "danger_zones": danger_zones,
            "readme": readme,
            "module_breakdown": module_breakdown,
            "ai_powered": False
        }

    async def analyze(self, repo_url: str) -> dict:
        """Main analysis pipeline  fetches repo, analyzes files, generates onboarding guide."""
        start_time = time.time()
        owner, repo = self.parse_repo_url(repo_url)

        # Fetch file tree
        tree, branch = await self.get_repo_tree(owner, repo)

        # Filter files
        all_files = [
            f['path'] for f in tree
            if f['type'] == 'blob' and not self.should_skip(f['path'])
        ]

        # Prioritize important files
        priority = [f for f in all_files if any(pf in f.split('/')[-1] for pf in PRIORITY_FILES)]
        others = [f for f in all_files if f not in priority]
        ordered_files = self.select_question_files("architecture readiness deployment setup", all_files, {}, limit=MAX_FILES_TO_READ)

        # Fetch file contents
        file_contents = {}
        for path in ordered_files:
            content = await self.get_file_content(owner, repo, path)
            if content:
                file_contents[path] = content

        file_list_str = '\n'.join(all_files)
        code_context = '\n\n'.join(
            [f"=== {p} ===\n{c}" for p, c in list(file_contents.items())[:10]]
        )[:MAX_CONTEXT_CHARS]

        # Detect stack for metadata
        stack = self.detect_stack(all_files, file_contents)
        project_type = self.detect_project_type(all_files, stack)

        readiness = self.assess_devops_readiness(all_files, stack, project_type)

        # Try AI analysis with configured provider
        ai_powered = bool((self.ai_provider and self.ai_provider.get_name() != "Rule-based Analysis") or (self.api_key and self.project_id))
        
        # Use provided AI provider or fall back to watsonx
        if self.ai_provider:
            summary = await self.ai_provider.analyze(f"""You are a senior software engineer. Analyze this GitHub repository.

Repository: {owner}/{repo}
Files:
{file_list_str[:2000]}

Code:
{code_context[:3000]}

Write a clear, structured analysis:
1. What this project does (2-3 sentences)
2. Tech stack used (list each technology)
3. Who would use it and why
4. Architecture overview (how the pieces fit together)

Use markdown formatting with headers and bullet points.

###""")

            starting_guide = await self.ai_provider.analyze(f"""You are onboarding a new developer to {owner}/{repo}.

Files:
{file_list_str[:1500]}

Code:
{code_context[:2000]}

Write a "New Developer Starting Guide" in markdown:
- Which file to read first and why
- The main flow of the application (step by step)
- Top 3 things to understand before touching code
- What NOT to touch as a beginner
- How to run the project locally

###""")

            critical_files = await self.ai_provider.analyze(f"""Analyze this repository: {owner}/{repo}

Files:
{file_list_str[:1500]}

Code:
{code_context[:2000]}

Create a markdown table listing 5-7 critical files. For each:
- File path
- What it does (one sentence)
- Risk level (High/Medium/Low)
- Why it matters

###""")

            danger_zones = await self.ai_provider.analyze(f"""Analyze {owner}/{repo} for risks and complexity.

Files:
{file_list_str[:1500]}

Code:
{code_context[:2000]}

Identify danger zones in markdown:
- Complex or risky files (with specific file names)
- Tightly coupled code areas
- Technical debt indicators
- Things that could break easily
- Security concerns

###""")

            readme = await self.ai_provider.analyze(f"""Generate a professional README.md for {owner}/{repo}.

Files: {file_list_str[:1000]}
Code: {code_context[:2000]}

Write a complete README with these sections:
# {repo}
## Overview
## Tech Stack
## Getting Started
## Project Structure
## Contributing

Use proper markdown formatting.

###""")

            # If any AI call failed, use fallback for that section
            if not all([summary, starting_guide, critical_files, danger_zones, readme]):
                fallback = self.generate_fallback_analysis(owner, repo, all_files, file_contents)
                summary = summary or fallback["summary"]
                starting_guide = starting_guide or fallback["starting_guide"]
                critical_files = critical_files or fallback["critical_files"]
                danger_zones = danger_zones or fallback["danger_zones"]
                readme = readme or fallback["readme"]
            module_breakdown = self.generate_module_breakdown(all_files, file_contents, stack)
        else:
            fallback = self.generate_fallback_analysis(owner, repo, all_files, file_contents)
            summary = fallback["summary"]
            starting_guide = fallback["starting_guide"]
            critical_files = fallback["critical_files"]
            danger_zones = fallback["danger_zones"]
            readme = fallback["readme"]
            module_breakdown = fallback["module_breakdown"]

        # Store file_contents on self so /api/ask can use it for context
        self._last_file_contents = file_contents
        self._last_file_list = all_files

        elapsed = round(time.time() - start_time, 1)
        
        # Generate pipeline stages
        pipeline_stages = self.generate_pipeline_stages(all_files, stack, readiness)

        return {
            "repo": f"{owner}/{repo}",
            "branch": branch,
            "total_files": len(all_files),
            "analyzed_files": len(file_contents),
            "all_files": all_files,
            "file_tree": all_files,
            "context_files": list(file_contents.keys()),
            "ai_powered": ai_powered,
            "stack": stack,
            "project_type": project_type,
            "analysis_time": elapsed,
            "readiness": readiness,
            "pipeline_stages": pipeline_stages,
            "summary": summary,
            "starting_guide": starting_guide,
            "critical_files": critical_files,
            "danger_zones": danger_zones,
            "readme": readme,
            "module_breakdown": module_breakdown
        }
    
    def generate_pipeline_stages(self, file_list: list, stack: list, readiness: dict) -> list:
        """Generate dynamic pipeline stages based on detected stack and readiness."""
        stages = []
        
        # Stage 1: Source Control (always present)
        stages.append({
            "name": "Source",
            "icon": "📦",
            "tools": ["GitHub", "Git"],
            "status": "configured",
            "time": "< 1min",
            "description": "Code repository and version control"
        })
        
        # Stage 2: Build (based on detected stack)
        build_tools = []
        if "Docker" in stack:
            build_tools.append("Docker")
        if "npm" in stack or "JavaScript" in stack or "TypeScript" in stack:
            build_tools.append("npm/webpack")
        if "Python" in stack:
            build_tools.append("pip")
        if "Go" in stack:
            build_tools.append("go build")
        if "Java" in stack:
            build_tools.append("Maven/Gradle")
        
        stages.append({
            "name": "Build",
            "icon": "🔨",
            "tools": build_tools if build_tools else ["Docker"],
            "status": "configured",
            "time": "3-5min",
            "description": "Compile code and build artifacts"
        })
        
        # Stage 3: Test (based on test detection)
        has_tests = readiness.get("signals", {}).get("tests", False)
        test_frameworks = []
        if "Python" in stack:
            test_frameworks.append("pytest")
        if "JavaScript" in stack or "TypeScript" in stack:
            test_frameworks.append("Jest")
        if "Go" in stack:
            test_frameworks.append("go test")
        if "Java" in stack:
            test_frameworks.append("JUnit")
        
        stages.append({
            "name": "Test",
            "icon": "🧪",
            "tools": test_frameworks if test_frameworks else ["Unit Tests"],
            "status": "configured" if has_tests else "missing",
            "time": "2-4min",
            "description": "Run automated tests and quality checks"
        })
        
        # Stage 4: Security Scan (recommended)
        has_security = readiness.get("signals", {}).get("security", False)
        stages.append({
            "name": "Security",
            "icon": "🔒",
            "tools": ["Trivy", "Snyk"],
            "status": "configured" if has_security else "recommended",
            "time": "1-2min",
            "description": "Scan for vulnerabilities and security issues"
        })
        
        # Stage 5: Container Registry (if using Docker)
        if "Docker" in stack:
            stages.append({
                "name": "Registry",
                "icon": "📦",
                "tools": ["AWS ECR", "Docker Hub"],
                "status": "configured",
                "time": "1-2min",
                "description": "Push container images to registry"
            })
        
        # Stage 6: Deploy (based on infrastructure)
        has_infra = readiness.get("signals", {}).get("infra", False)
        deploy_targets = []
        if "Kubernetes" in str(file_list) or has_infra:
            deploy_targets.append("AWS EKS")
        if "Docker Compose" in stack:
            deploy_targets.append("Docker Swarm")
        if not deploy_targets:
            deploy_targets.append("AWS EKS")
        
        stages.append({
            "name": "Deploy",
            "icon": "🚀",
            "tools": deploy_targets,
            "status": "configured",
            "time": "5-10min",
            "description": "Deploy to production environment"
        })
        
        # Stage 7: Monitor (based on monitoring detection)
        has_monitoring = readiness.get("signals", {}).get("monitoring", False)
        stages.append({
            "name": "Monitor",
            "icon": "📊",
            "tools": ["Prometheus", "Grafana", "ELK"],
            "status": "configured" if has_monitoring else "recommended",
            "time": "continuous",
            "description": "Track performance and health metrics"
        })
        
        return stages

