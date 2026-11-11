"""
Step 3 Unit & Integration Tests: AI Infrastructure Requirement Parser
Tests Pydantic models, JSON extraction, mocked model responses, semantic validation,
missing field detection, clarifications, and API endpoint integration.
"""
import json
from unittest.mock import MagicMock
from requirement_parser import (
    ServiceType, Environment, DatabaseType, NetworkExposure, MonitoringPreference,
    InfrastructureSpec, ParseResult, extract_json_from_text, build_llm_prompt,
    rule_based_parse, validate_and_build_spec, parse_infrastructure_requirements
)
from main import app, ParseRequirementRequest


def run_sync(coro):
    """Executes a coroutine synchronously without event loop socketpair overhead."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


def test_pydantic_spec_validation_and_defaults():
    """Verify that InfrastructureSpec validates defaults and fields correctly."""
    spec = InfrastructureSpec(
        service_name="Payment-Gateway API!!",
        service_type=ServiceType.WEB_API,
        environment=Environment.PRODUCTION,
        replica_count=3,
        database=DatabaseType.POSTGRES,
        network_exposure=NetworkExposure.LOAD_BALANCER,
        monitoring=MonitoringPreference.PROMETHEUS_GRAFANA,
        raw_request="Deploy payment gateway"
    )
    # Name must be sanitized to DNS-compliant slug
    assert spec.service_name == "payment-gateway-api"
    assert spec.replica_count == 3
    assert spec.environment == Environment.PRODUCTION
    assert spec.database == DatabaseType.POSTGRES
    assert spec.network_exposure == NetworkExposure.LOAD_BALANCER
    assert spec.monitoring == MonitoringPreference.PROMETHEUS_GRAFANA
    assert spec.confidence_score == 1.0


def test_extract_json_from_clean_and_fenced_markdown():
    """Verify JSON extraction handles raw JSON, markdown fences, and embedded text."""
    # 1. Clean JSON
    raw = '{"service_name": "auth-svc", "service_type": "web-api", "environment": "staging", "replica_count": 2}'
    data = extract_json_from_text(raw)
    assert data is not None
    assert data["service_name"] == "auth-svc"

    # 2. Markdown fenced with ```json
    fenced = """Here is the extracted infrastructure specification:
```json
{
  "service_name": "order-api",
  "service_type": "web-api",
  "environment": "production",
  "replica_count": 4,
  "database": "postgres"
}
```
Hope this helps!"""
    data_fenced = extract_json_from_text(fenced)
    assert data_fenced is not None
    assert data_fenced["service_name"] == "order-api"
    assert data_fenced["replica_count"] == 4

    # 3. Invalid text returns None without crashing
    assert extract_json_from_text("This is not JSON at all.") is None


def test_mocked_ollama_model_success():
    """Verify parser with mocked Ollama model returning clean JSON."""
    mock_provider = MagicMock()
    mock_provider.get_name.return_value = "Ollama llama3"
    mock_provider.model = "llama3"

    async def mock_analyze(prompt):
        return json.dumps({
            "service_name": "billing-service",
            "service_type": "worker",
            "environment": "staging",
            "replica_count": 2,
            "database": "redis",
            "network_exposure": "cluster-ip",
            "monitoring": "basic"
        })

    mock_provider.analyze = mock_analyze

    user_req = "Deploy a billing background worker in staging with Redis cache and 2 replicas"
    result = run_sync(parse_infrastructure_requirements(user_req, ai_provider=mock_provider))

    assert result.success is True
    assert result.spec is not None
    assert result.spec.service_name == "billing-service"
    assert result.spec.service_type == ServiceType.WORKER
    assert result.spec.database == DatabaseType.REDIS
    assert result.spec.environment == Environment.STAGING
    assert result.spec.replica_count == 2
    assert result.parser_used == "llama3"


def test_mocked_model_failure_triggers_rule_fallback():
    """Verify that if LLM fails or returns garbage, rule-based fallback succeeds."""
    mock_provider = MagicMock()
    mock_provider.get_name.return_value = "Ollama llama3"

    async def mock_fail(prompt):
        return "I apologize, but as an AI I cannot help with that."

    mock_provider.analyze = mock_fail

    user_req = "Need a high-availability Python FastAPI service with PostgreSQL database in production, 3 replicas, public Ingress exposure, Prometheus metrics"
    result = run_sync(parse_infrastructure_requirements(user_req, ai_provider=mock_provider))

    assert result.success is True
    assert result.spec is not None
    assert result.spec.service_type == ServiceType.WEB_API
    assert result.spec.database == DatabaseType.POSTGRES
    assert result.spec.environment == Environment.PRODUCTION
    assert result.spec.replica_count == 3
    assert result.spec.network_exposure == NetworkExposure.LOAD_BALANCER
    assert result.spec.monitoring == MonitoringPreference.PROMETHEUS_GRAFANA
    assert result.parser_used == "rule-based"


def test_missing_fields_and_vague_requests():
    """Verify that requests missing key information flag missing fields and request clarifications."""
    # 1. Very brief / empty prompt
    brief_result = validate_and_build_spec({}, "app", parser_used="rule-based")
    assert brief_result.success is False
    assert "service_type" in brief_result.missing_fields
    assert any("brief" in c.lower() or "details" in c.lower() for c in brief_result.clarifications_needed)

    # 2. Vague prompt missing fields
    vague_result = validate_and_build_spec({}, "deploy something in the cloud", parser_used="rule-based")
    assert "service_type" in vague_result.missing_fields
    assert "environment" in vague_result.missing_fields
    assert any("service type" in c.lower() for c in vague_result.clarifications_needed)


def test_semantic_clarifications_and_warnings():
    """Verify safety warnings for 1-replica production and invalid replica bounds."""
    # 1. Single replica in production generates a warning
    data_prod_single = {
        "service_name": "critical-api",
        "service_type": "web-api",
        "environment": "production",
        "replica_count": 1,
        "database": "postgres",
        "network_exposure": "load-balancer",
        "monitoring": "prometheus-grafana"
    }
    result = validate_and_build_spec(data_prod_single, "Deploy single pod prod", parser_used="test")
    assert any("at least 2 replicas" in c for c in result.clarifications_needed)

    # 2. Out-of-bounds replica count gets clamped and flagged
    data_overflow = {
        "service_name": "overflow-api",
        "service_type": "web-api",
        "environment": "development",
        "replica_count": 999
    }
    result_overflow = validate_and_build_spec(data_overflow, "Deploy with 999 replicas", parser_used="test")
    assert "replica_count" in result_overflow.invalid_fields
    assert result_overflow.spec.replica_count == 20  # Clamped to upper bound


def test_rule_based_keyword_variations():
    """Verify heuristic extraction detects diverse terminology."""
    # Celery queue worker with Redis
    r1 = rule_based_parse("Celery worker consumer with Redis queue, 4 instances in dev")
    assert r1.get("service_type") == ServiceType.WORKER.value
    assert r1.get("database") == DatabaseType.REDIS.value
    assert r1.get("replica_count") == 4
    assert r1.get("environment") == Environment.DEVELOPMENT.value

    # React client SPA with no db
    r2 = rule_based_parse("React frontend web app with no database, exposed via Ingress in staging")
    assert r2.get("service_type") == ServiceType.FRONTEND_SPA.value
    assert r2.get("database") == DatabaseType.NONE.value
    assert r2.get("network_exposure") == NetworkExposure.LOAD_BALANCER.value
    assert r2.get("environment") == Environment.STAGING.value


def test_api_route_registered_and_schema():
    """Verify /api/infrastructure/parse is registered on the FastAPI app."""
    routes = {route.path: route for route in app.routes}
    assert "/api/infrastructure/parse" in routes
    route = routes["/api/infrastructure/parse"]
    assert "POST" in route.methods
