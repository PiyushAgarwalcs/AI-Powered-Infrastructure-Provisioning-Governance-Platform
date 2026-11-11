"""
Config Usage Instructions for ShipSage
Provides clear, actionable guidance for each generated configuration file
"""

CONFIG_USAGE = {
    "dockerfile": {
        "icon": "🐳",
        "title": "Dockerfile",
        "what": "Creates a production-ready Docker image with multi-stage build for optimal size and security",
        "steps": [
            "Save as `Dockerfile` in your project root",
            "Build: `docker build -t myapp:latest .`",
            "Run: `docker run -p 8000:8000 myapp:latest`",
            "Test: `curl http://localhost:8000/health`"
        ],
        "next": "Push to Docker Hub/AWS ECR → Use in Kubernetes → Integrate with CI/CD",
        "tips": [
            "Multi-stage build reduces image size by 60-80%",
            "Non-root user improves security",
            "Health check enables container orchestration"
        ],
        "common_issues": [
            "Port conflicts: Change `-p 8000:8000` to your port",
            "Build fails: Check dependencies in requirements.txt/package.json",
            "Permission denied: Run with `sudo` or add user to docker group"
        ]
    },
    
    "compose": {
        "icon": "🐙",
        "title": "Docker Compose",
        "what": "Orchestrates multi-container applications with networking, volumes, and environment configuration",
        "steps": [
            "Save as `docker-compose.yml` in project root",
            "Start: `docker-compose up -d`",
            "View logs: `docker-compose logs -f`",
            "Stop: `docker-compose down`"
        ],
        "next": "Add database services → Configure volumes → Set up reverse proxy",
        "tips": [
            "Use `.env` file for environment variables",
            "Named volumes persist data across restarts",
            "Networks isolate services for security"
        ],
        "common_issues": [
            "Port already in use: Change ports in compose file",
            "Volume permission errors: Check file ownership",
            "Service won't start: Check `docker-compose logs <service>`"
        ]
    },
    
    "kubernetes": {
        "icon": "☸️",
        "title": "Kubernetes Manifests",
        "what": "Complete K8s deployment with service, ingress, HPA, and ConfigMap for production orchestration",
        "steps": [
            "Save as `k8s-manifests.yaml`",
            "Apply: `kubectl apply -f k8s-manifests.yaml`",
            "Check status: `kubectl get pods,svc,ingress`",
            "View logs: `kubectl logs -f deployment/myapp`"
        ],
        "next": "Configure ingress hostname → Set resource limits → Add liveness probes",
        "tips": [
            "HPA automatically scales based on CPU/memory",
            "ConfigMap separates config from code",
            "Ingress provides external access with SSL"
        ],
        "common_issues": [
            "ImagePullBackOff: Push image to registry first",
            "CrashLoopBackOff: Check logs with `kubectl logs`",
            "Pending pods: Check resource availability with `kubectl describe pod`"
        ]
    },
    
    "cicd": {
        "icon": "🔄",
        "title": "GitHub Actions CI/CD",
        "what": "Automated pipeline that builds, tests, and deploys on every push to main/develop branches",
        "steps": [
            "Save as `.github/workflows/main.yml`",
            "Add secrets in GitHub: Settings → Secrets → Actions",
            "Required secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ECR_REPOSITORY`, `EKS_CLUSTER`",
            "Push to trigger: `git push origin main`"
        ],
        "next": "Add test stage → Configure deployment environments → Set up notifications",
        "tips": [
            "Secrets are encrypted and never exposed in logs",
            "Workflow runs on every push/PR to specified branches",
            "Failed builds block deployment automatically"
        ],
        "common_issues": [
            "Workflow not running: Check branch name matches trigger",
            "Secret not found: Verify secret name matches exactly",
            "AWS auth fails: Check IAM permissions for EKS/ECR"
        ]
    },
    
    "terraform": {
        "icon": "🏗️",
        "title": "AWS Terraform Infrastructure",
        "what": "Infrastructure as Code for VPC, EKS cluster, RDS database, S3 buckets, and networking",
        "steps": [
            "Save as `main.tf` in `terraform/` directory",
            "Initialize: `terraform init`",
            "Plan: `terraform plan` (review changes)",
            "Apply: `terraform apply` (creates infrastructure)",
            "Destroy: `terraform destroy` (when done)"
        ],
        "next": "Configure backend state → Add monitoring → Set up backups",
        "tips": [
            "Always run `terraform plan` before `apply`",
            "Use remote state (S3) for team collaboration",
            "Tag all resources for cost tracking"
        ],
        "common_issues": [
            "AWS credentials: Configure with `aws configure`",
            "Resource already exists: Import with `terraform import`",
            "State locked: Another apply is running or crashed"
        ]
    },
    
    "monitoring": {
        "icon": "📊",
        "title": "ELK Stack & Prometheus",
        "what": "Complete observability stack with logs (ELK), metrics (Prometheus), and dashboards (Grafana)",
        "steps": [
            "Save as `monitoring.yml`",
            "Deploy: `docker-compose -f monitoring.yml up -d`",
            "Access Kibana: http://localhost:5601",
            "Access Grafana: http://localhost:3000 (admin/admin)",
            "Access Prometheus: http://localhost:9090"
        ],
        "next": "Configure log retention → Create custom dashboards → Set up alerts",
        "tips": [
            "Elasticsearch stores 7 days of logs by default",
            "Grafana has pre-built dashboards for common metrics",
            "Prometheus scrapes metrics every 15 seconds"
        ],
        "common_issues": [
            "Elasticsearch won't start: Increase Docker memory to 4GB+",
            "No logs appearing: Check application log format",
            "High disk usage: Configure log rotation and retention"
        ]
    },
    
    "env_config": {
        "icon": "⚙️",
        "title": "Environment & Nginx Config",
        "what": "Environment template for secrets/config and Nginx reverse proxy for production deployment",
        "steps": [
            "Copy `.env.template` to `.env`",
            "Fill in all values (never commit `.env` to git)",
            "Save `nginx.conf` to `/etc/nginx/sites-available/`",
            "Enable: `sudo ln -s /etc/nginx/sites-available/nginx.conf /etc/nginx/sites-enabled/`",
            "Test: `sudo nginx -t`",
            "Reload: `sudo systemctl reload nginx`"
        ],
        "next": "Add SSL certificate → Configure rate limiting → Set up caching",
        "tips": [
            "Use strong random values for SECRET_KEY",
            "Store sensitive values in AWS Secrets Manager",
            "Nginx handles SSL termination and load balancing"
        ],
        "common_issues": [
            "502 Bad Gateway: Check if app is running on correct port",
            "Permission denied: Check file ownership and SELinux",
            "SSL errors: Verify certificate paths and permissions"
        ]
    }
}

def get_usage_html(config_type: str) -> str:
    """Generate HTML for config usage instructions"""
    if config_type not in CONFIG_USAGE:
        return ""
    
    usage = CONFIG_USAGE[config_type]
    
    html = f"""
    <div class="config-usage-card">
      <div class="usage-header">
        <div class="usage-icon">{usage['icon']}</div>
        <div>
          <div class="usage-title">What This Does</div>
          <div class="usage-desc">{usage['what']}</div>
        </div>
      </div>
      
      <div class="usage-steps">
        <div class="usage-step-title">🚀 How to Use</div>
"""
    
    for i, step in enumerate(usage['steps'], 1):
        html += f'        <div class="usage-step"><span class="step-num">{i}</span> {step}</div>\n'
    
    html += f"""      </div>
      
      <div class="usage-next">
        <strong>Next Steps:</strong> {usage['next']}
      </div>
      
      <details class="usage-details">
        <summary>💡 Pro Tips</summary>
        <ul>
"""
    
    for tip in usage['tips']:
        html += f'          <li>{tip}</li>\n'
    
    html += """        </ul>
      </details>
      
      <details class="usage-details">
        <summary>⚠️ Common Issues</summary>
        <ul>
"""
    
    for issue in usage['common_issues']:
        html += f'          <li>{issue}</li>\n'
    
    html += """        </ul>
      </details>
    </div>
"""
    
    return html

# Made with Bob
