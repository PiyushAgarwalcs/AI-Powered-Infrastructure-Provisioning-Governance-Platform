import json

from fastapi.testclient import TestClient

import main
from infra_platform.infrastructure.requirement_parser import validate_and_build_spec
from infra_platform.infrastructure.terraform_runner import build_mock_plan_json


class MockProvider:
    model = "mock-llm"

    def __init__(self, response):
        self.response = response

    def get_name(self):
        return "Mock Ollama"

    async def analyze(self, prompt):
        return self.response


def install_mock_provider(monkeypatch, response):
    monkeypatch.setattr(
        main.AIProviderFactory,
        "create_provider",
        lambda *args, **kwargs: MockProvider(response),
    )


def test_invalid_llm_json_falls_back_to_rule_parser_api(monkeypatch):
    install_mock_provider(monkeypatch, "{ invalid JSON")
    client = TestClient(main.app)

    response = client.post(
        "/api/infrastructure/parse",
        json={
            "prompt": (
                "Deploy a FastAPI orders service in development with two replicas, "
                "no database, internal networking, and basic monitoring"
            ),
            "ai_provider": "ollama",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["parser_used"] == "rule-based"
    assert result["raw_llm_output"] == "{ invalid JSON"
    assert result["spec"]["service_type"] == "web-api"


def test_invalid_llm_enum_fields_return_validation_details_not_server_error(monkeypatch):
    install_mock_provider(
        monkeypatch,
        json.dumps({
            "service_name": ["orders-api"],
            "service_type": "spaceship",
            "environment": "moon",
            "replica_count": 2,
            "database": "none",
            "network_exposure": "cluster-ip",
            "monitoring": "basic",
        }),
    )
    client = TestClient(main.app)

    response = client.post(
        "/api/infrastructure/parse",
        json={
            "prompt": "Deploy an orders API",
            "ai_provider": "ollama",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert {"service_name", "service_type", "environment"}.issubset(
        result["invalid_fields"]
    )
    assert result["spec"]["service_name"] == "infra-service"
    assert result["spec"]["service_type"] == "web-api"
    assert result["spec"]["environment"] == "production"


def test_generate_endpoint_rejects_invalid_infrastructure_spec():
    response = TestClient(main.app).post(
        "/api/infrastructure/generate",
        json={
            "service_name": "invalid-api",
            "service_type": "web-api",
            "environment": "development",
            "replica_count": 0,
            "database": "none",
            "network_exposure": "cluster-ip",
            "monitoring": "basic",
        },
    )

    assert response.status_code == 422


def test_oversized_service_name_is_rejected_by_api_and_flagged_by_parser(monkeypatch):
    oversized_name = "a" * 64
    response = TestClient(main.app).post(
        "/api/infrastructure/generate",
        json={
            "service_name": oversized_name,
            "service_type": "web-api",
            "environment": "development",
            "replica_count": 1,
            "database": "none",
            "network_exposure": "cluster-ip",
            "monitoring": "basic",
        },
    )
    assert response.status_code == 422

    parsed = validate_and_build_spec(
        {
            "service_name": oversized_name,
            "service_type": "web-api",
            "environment": "development",
            "replica_count": 1,
            "database": "none",
            "network_exposure": "cluster-ip",
            "monitoring": "basic",
        },
        "Deploy a service with an oversized name",
        parser_used="mock-llm",
    )
    assert parsed.success is False
    assert "service_name" in parsed.invalid_fields
    assert parsed.spec.service_name == "infra-service"


def test_request_to_terraform_plan_and_approval_workflow(monkeypatch):
    provider_output = {
        "service_name": "orders-api",
        "service_type": "web-api",
        "environment": "development",
        "replica_count": 2,
        "database": "none",
        "network_exposure": "cluster-ip",
        "monitoring": "basic",
    }
    install_mock_provider(monkeypatch, json.dumps(provider_output))
    client = TestClient(main.app)

    parsed = client.post(
        "/api/infrastructure/parse",
        json={
            "prompt": (
                "Deploy orders-api as a FastAPI web API in development with two replicas, "
                "no database, internal networking, and basic monitoring"
            ),
            "ai_provider": "ollama",
        },
    )
    assert parsed.status_code == 200
    spec = parsed.json()["spec"]
    assert parsed.json()["success"] is True

    generated = client.post("/api/infrastructure/generate", json=spec)
    assert generated.status_code == 200
    generated_data = generated.json()
    assert generated_data["success"] is True
    terraform_hcl = generated_data["configs"]["aws_terraform"]

    analyzed = client.post(
        "/api/terraform/analyze",
        json={
            "terraform_hcl": terraform_hcl,
            "service_name": spec["service_name"],
            "use_cli": False,
        },
    )
    assert analyzed.status_code == 200
    blast_radius = analyzed.json()["blast_radius"]

    plan_json = build_mock_plan_json(terraform_hcl, spec["service_name"])
    plan_analysis = client.post(
        "/api/terraform/blast-radius",
        json={"plan_json": plan_json, "service_name": spec["service_name"]},
    )
    assert plan_analysis.status_code == 200
    assert plan_analysis.json()["blast_radius"]["adds"] == blast_radius["adds"]

    evaluated = client.post(
        "/api/governance/evaluate",
        json={
            "spec": spec,
            "blast_radius": blast_radius,
            "plan_json": plan_json,
            "requester": "workflow-test",
        },
    )
    assert evaluated.status_code == 200
    approval = evaluated.json()
    assert approval["provisioning_allowed"] is True
    assert approval["approval_status"] == "pending"

    approved = client.post(
        "/api/governance/approve",
        json={
            "approval_id": approval["approval_id"],
            "approver": "human-reviewer",
            "current_plan_json": plan_json,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["success"] is True
