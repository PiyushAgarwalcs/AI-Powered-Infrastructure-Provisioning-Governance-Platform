"""
Step 2 Integration Tests: Product Rebranding & Infrastructure Request Interface
"""
import pytest
import os
from main import app, InfrastructureRequest
from generators import (
    gen_dockerfile, gen_compose, gen_kubernetes,
    gen_cicd, gen_aws_terraform, gen_monitoring, gen_env_and_nginx
)


def test_html_rebranding():
    """Verify that templates/index.html is rebranded to the new title and styling."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
    assert os.path.exists(html_path), "templates/index.html must exist"
    
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Rebranded title
    assert "<title>AI-Powered Infrastructure Provisioning & Governance Platform</title>" in html
    
    # Rebranded headers
    assert "Infra<span>Govern</span>" in html
    assert "Infrastructure <span>Provisioning & Governance</span>" in html


def test_html_form_elements():
    """Verify that all required infrastructure request inputs are present in the UI."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Natural-language infrastructure request field
    assert 'id="naturalLanguageRequest"' in html
    
    # 2. Service type selection
    assert 'id="serviceType"' in html
    assert 'value="web-api"' in html
    assert 'value="frontend-spa"' in html
    assert 'value="worker"' in html
    assert 'value="full-stack"' in html

    # 3. Environment selection
    assert 'id="environment"' in html
    assert 'value="production"' in html
    assert 'value="staging"' in html
    assert 'value="development"' in html

    # 4. Replica count
    assert 'id="replicaCount"' in html

    # 5. Database selection
    assert 'id="databaseType"' in html
    assert 'value="postgres"' in html
    assert 'value="mysql"' in html
    assert 'value="mongodb"' in html
    assert 'value="redis"' in html
    assert 'value="none"' in html

    # 6. Network exposure selection
    assert 'id="networkExposure"' in html
    assert 'value="load-balancer"' in html
    assert 'value="cluster-ip"' in html
    assert 'value="node-port"' in html

    # 7. Monitoring preference
    assert 'id="monitoringPreference"' in html
    assert 'value="prometheus-grafana"' in html
    assert 'value="basic"' in html
    assert 'value="none"' in html

    # 8. Service name input
    assert 'id="serviceName"' in html

    # 9. Form submission & specification banner
    assert "submitProvisionRequest()" in html
    assert 'id="infra-spec-card"' in html


def test_pydantic_infrastructure_model():
    """Verify that the InfrastructureRequest model parses and validates parameters."""
    # Test defaults
    default_req = InfrastructureRequest()
    assert default_req.service_type == "web-api"
    assert default_req.environment == "production"
    assert default_req.replica_count == 2
    assert default_req.database == "postgres"
    assert default_req.network_exposure == "load-balancer"
    assert default_req.monitoring == "prometheus-grafana"

    # Test customized specification
    custom_req = InfrastructureRequest(
        natural_language_request="Deploy a scalable Redis caching worker with 5 replicas in staging internal only",
        service_type="worker",
        environment="staging",
        replica_count=5,
        database="redis",
        network_exposure="cluster-ip",
        monitoring="basic",
        service_name="cache-worker"
    )
    assert custom_req.service_name == "cache-worker"
    assert custom_req.replica_count == 5
    assert custom_req.environment == "staging"
    assert custom_req.database == "redis"
    assert custom_req.network_exposure == "cluster-ip"


def test_backend_routes_registered():
    """Verify that the FastAPI app registers the infrastructure provisioning routes."""
    routes = [route.path for route in app.routes]
    
    assert "/api/provision/request" in routes
    assert "/health" in routes
    assert "/" in routes


def test_generators_integration():
    """Verify that generators successfully compile manifests for requested infrastructure."""
    stack = ["Python", "FastAPI", "PostgreSQL", "Prometheus"]
    files = ["main.py", "requirements.txt", "Dockerfile", "database.py"]
    ptype = "FastAPI"

    dockerfile = gen_dockerfile(stack, ptype, files)
    assert len(dockerfile) > 50
    assert "FROM" in dockerfile

    k8s = gen_kubernetes(stack, ptype)
    assert "kind: Deployment" in k8s
    assert "kind: Service" in k8s

    tf = gen_aws_terraform(stack, files)
    assert "resource \"aws_db_instance\"" in tf

    compose = gen_compose(stack, files)
    assert "postgres:" in compose

    monitoring = gen_monitoring(stack)
    assert "prometheus" in monitoring.lower()


def test_service_type_and_db_variations():
    """Verify that different service types and database selections produce corresponding configs."""
    # 1. Frontend SPA without database
    stack_spa = ["JavaScript", "React", "Node.js"]
    df_spa = gen_dockerfile(stack_spa, "React", ["package.json"])
    assert "node" in df_spa.lower()

    # 2. Worker with Redis
    stack_worker = ["Python", "Worker", "Redis"]
    compose_worker = gen_compose(stack_worker, ["main.py", "requirements.txt"])
    assert "redis:" in compose_worker

    # 3. Web API with PostgreSQL
    stack_pg = ["Python", "FastAPI", "PostgreSQL"]
    compose_pg = gen_compose(stack_pg, ["main.py", "requirements.txt"])
    assert "postgres:" in compose_pg

    # 4. Web API with MongoDB
    stack_mongo = ["Python", "FastAPI", "MongoDB"]
    compose_mongo = gen_compose(stack_mongo, ["main.py", "requirements.txt"])
    assert "mongo:" in compose_mongo

