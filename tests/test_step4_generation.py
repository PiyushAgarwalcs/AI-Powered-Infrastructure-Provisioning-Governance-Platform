"""
Step 4 Unit & Integration Tests: Infrastructure Configuration Generation
Tests spec-driven generation of Terraform, Kubernetes, Docker, and Compose,
alongside syntax and schema validators, download functionality, and API endpoints.
"""
import io
import zipfile
import pytest

from requirement_parser import (
    InfrastructureSpec, ServiceType, Environment, DatabaseType,
    NetworkExposure, MonitoringPreference
)
from generators import (
    generate_terraform_for_spec, generate_kubernetes_for_spec,
    generate_dockerfile_for_spec, generate_compose_for_spec,
    generate_all_spec_configurations
)
from config_validator import (
    validate_kubernetes_manifests, validate_terraform_code,
    validate_dockerfile_syntax, validate_compose_syntax,
    validate_all_spec_configurations
)
from main import (
    generate_infrastructure_endpoint, download_infrastructure_configs,
    provision_request, InfrastructureRequest
)


def run_sync(coro):
    """Executes a coroutine synchronously without event loop socketpair overhead."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


@pytest.fixture
def sample_spec():
    return InfrastructureSpec(
        service_name="payment-service",
        service_type=ServiceType.WEB_API,
        environment=Environment.PRODUCTION,
        replica_count=3,
        database=DatabaseType.POSTGRES,
        network_exposure=NetworkExposure.LOAD_BALANCER,
        monitoring=MonitoringPreference.PROMETHEUS_GRAFANA,
        raw_prompt="Deploy Python FastAPI with PostgreSQL in production with 3 replicas",
        enable_autoscaling=True,
        min_replicas=2,
        max_replicas=6
    )


def test_terraform_generation_with_postgres(sample_spec):
    """Verify Terraform configuration includes VPC, ECR, Security Groups, and RDS PostgreSQL."""
    tf_code = generate_terraform_for_spec(sample_spec)
    assert 'provider "aws"' in tf_code
    assert 'resource "aws_vpc" "main"' in tf_code
    assert 'resource "aws_subnet"' in tf_code
    assert 'resource "aws_security_group" "app"' in tf_code
    assert 'resource "aws_security_group" "db"' in tf_code
    assert 'resource "aws_ecr_repository" "app"' in tf_code
    assert 'resource "aws_db_instance" "postgres"' in tf_code
    assert 'engine                 = "postgres"' in tf_code
    assert 'output "db_endpoint"' in tf_code
    assert 'payment-service' in tf_code


def test_terraform_generation_no_database():
    """Verify Terraform configuration omits RDS when database is none."""
    spec = InfrastructureSpec(
        service_name="stateless-api",
        service_type=ServiceType.WEB_API,
        environment=Environment.DEVELOPMENT,
        replica_count=1,
        database=DatabaseType.NONE,
        network_exposure=NetworkExposure.CLUSTER_IP,
        monitoring=MonitoringPreference.NONE
    )
    tf_code = generate_terraform_for_spec(spec)
    assert 'resource "aws_vpc" "main"' in tf_code
    assert 'resource "aws_db_instance"' not in tf_code
    assert 'output "db_endpoint"' not in tf_code


def test_kubernetes_generation_with_postgres(sample_spec):
    """Verify Kubernetes manifests include Namespace, Deployment, Service, Postgres and HPA."""
    k8s_yaml = generate_kubernetes_for_spec(sample_spec)
    assert 'kind: Namespace' in k8s_yaml
    assert 'name: payment-service-production' in k8s_yaml
    assert 'kind: Deployment' in k8s_yaml
    assert 'replicas: 3' in k8s_yaml
    assert 'kind: Service' in k8s_yaml
    assert 'type: LoadBalancer' in k8s_yaml
    assert 'kind: ConfigMap' in k8s_yaml
    assert 'kind: Secret' in k8s_yaml
    assert 'kind: HorizontalPodAutoscaler' in k8s_yaml
    # Check embedded postgres for local testing
    assert 'app: postgres' in k8s_yaml
    assert 'image: postgres:16-alpine' in k8s_yaml


def test_kubernetes_internal_network_exposure():
    """Verify cluster-ip network exposure generates ClusterIP service."""
    spec = InfrastructureSpec(
        service_name="internal-worker",
        service_type=ServiceType.WORKER,
        environment=Environment.DEVELOPMENT,
        replica_count=1,
        database=DatabaseType.NONE,
        network_exposure=NetworkExposure.CLUSTER_IP,
        monitoring=MonitoringPreference.NONE
    )
    k8s_yaml = generate_kubernetes_for_spec(spec)
    assert 'type: ClusterIP' in k8s_yaml
    assert 'LoadBalancer' not in k8s_yaml


def test_dockerfile_and_compose_generation(sample_spec):
    """Verify Dockerfile and Docker Compose syntax and contents."""
    dockerfile = generate_dockerfile_for_spec(sample_spec)
    assert "FROM python:" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "EXPOSE 8000" in dockerfile

    compose = generate_compose_for_spec(sample_spec)
    assert "version:" in compose
    assert "services:" in compose
    assert "payment-service:" in compose
    assert "postgres:" in compose


def test_validator_kubernetes():
    """Verify Kubernetes validator checks valid YAML and catches syntax errors."""
    valid_yaml = """
apiVersion: v1
kind: Service
metadata:
  name: test-svc
spec:
  ports:
    - port: 80
"""
    result = validate_kubernetes_manifests(valid_yaml)
    assert result["valid"] is True
    assert result["document_count"] == 1

    invalid_yaml = """
apiVersion: v1
kind: Service
metadata:
  name: [unclosed list
"""
    result_invalid = validate_kubernetes_manifests(invalid_yaml)
    assert result_invalid["valid"] is False
    assert len(result_invalid["errors"]) > 0


def test_validator_terraform():
    """Verify Terraform validator checks block syntax and catches unclosed braces."""
    valid_tf = 'resource "aws_vpc" "test" {\n  cidr_block = "10.0.0.0/16"\n}\n'
    result = validate_terraform_code(valid_tf)
    assert result["valid"] is True
    assert result["resource_count"] == 1

    invalid_tf = 'resource "aws_vpc" "test" {\n  cidr_block = "10.0.0.0/16"\n'
    result_invalid = validate_terraform_code(invalid_tf)
    assert result_invalid["valid"] is False
    assert "Unclosed" in result_invalid["errors"][0]


def test_validator_dockerfile():
    """Verify Dockerfile validator catches missing FROM."""
    valid_df = "FROM python:3.10-slim\nWORKDIR /app\nCMD [\"python\", \"main.py\"]\n"
    assert validate_dockerfile_syntax(valid_df)["valid"] is True

    invalid_df = "WORKDIR /app\nCMD [\"python\", \"main.py\"]\n"
    res_inv = validate_dockerfile_syntax(invalid_df)
    assert res_inv["valid"] is False
    assert "Missing FROM" in res_inv["errors"][0]


def test_generate_all_spec_configurations(sample_spec):
    """Verify generate_all_spec_configurations returns complete config dictionary and all validate."""
    configs = generate_all_spec_configurations(sample_spec)
    expected_keys = {"dockerfile", "compose", "kubernetes", "aws_terraform", "cicd", "monitoring", "env_config"}
    assert expected_keys.issubset(configs.keys())

    validations = validate_all_spec_configurations(configs)
    assert validations["kubernetes"]["valid"] is True
    assert validations["aws_terraform"]["valid"] is True
    assert validations["dockerfile"]["valid"] is True
    assert validations["compose"]["valid"] is True


def test_generate_endpoint(sample_spec):
    """Test POST /api/infrastructure/generate endpoint handler."""
    response = run_sync(generate_infrastructure_endpoint(sample_spec))
    assert response["success"] is True
    assert "configs" in response
    assert "validations" in response
    assert response["validations"]["kubernetes"]["valid"] is True
    assert response["validations"]["aws_terraform"]["valid"] is True


def test_download_endpoint_zip_contents(sample_spec):
    """Test POST /api/infrastructure/download returns valid zip stream containing all files."""
    response = run_sync(download_infrastructure_configs(sample_spec))
    zip_bytes = io.BytesIO(response.body)

    with zipfile.ZipFile(zip_bytes, 'r') as zf:
        file_list = zf.namelist()
        assert any("Dockerfile" in name for name in file_list)
        assert any("docker-compose.yml" in name for name in file_list)
        assert any("k8s/manifests.yaml" in name for name in file_list)
        assert any("terraform/main.tf" in name for name in file_list)
        assert any("README.md" in name for name in file_list)


def test_provision_request_integration_with_spec():
    """Verify provision_request incorporates spec validation and spec configs."""
    req = InfrastructureRequest(
        natural_language_request="Deploy FastAPI orders service with PostgreSQL",
        service_name="orders-service",
        service_type="web-api",
        environment="staging",
        replica_count=2,
        database="postgres",
        network_exposure="load-balancer",
        monitoring="prometheus-grafana"
    )
    result = run_sync(provision_request(req))
    assert "validations" in result
    assert result["validations"]["kubernetes"]["valid"] is True
    assert result["validations"]["aws_terraform"]["valid"] is True
    assert "aws_db_instance" in result["aws_terraform"]
    assert "orders-service" in result["kubernetes"]
