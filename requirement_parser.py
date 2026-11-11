"""
AI Infrastructure Requirement Parser Module
Converts natural language infrastructure requests into validated Pydantic specifications.
Supports Ollama local LLMs with a deterministic heuristic fallback engine.
"""
from enum import Enum
import json
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ValidationInfo


class ServiceType(str, Enum):
    WEB_API = "web-api"
    FRONTEND_SPA = "frontend-spa"
    WORKER = "worker"
    FULL_STACK = "full-stack"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseType(str, Enum):
    NONE = "none"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"


class NetworkExposure(str, Enum):
    CLUSTER_IP = "cluster-ip"
    NODE_PORT = "node-port"
    LOAD_BALANCER = "load-balancer"


class MonitoringPreference(str, Enum):
    PROMETHEUS_GRAFANA = "prometheus-grafana"
    BASIC = "basic"
    NONE = "none"


class InfrastructureSpec(BaseModel):
    """Structured, validated specification for infrastructure provisioning."""
    service_name: str = Field(default="api-service", description="Canonical DNS-safe service identifier")
    service_type: ServiceType = Field(default=ServiceType.WEB_API, description="High-level architecture type")
    environment: Environment = Field(default=Environment.PRODUCTION, description="Deployment target tier")
    replica_count: int = Field(default=2, ge=1, le=20, description="Desired pod or instance count")
    database: DatabaseType = Field(default=DatabaseType.POSTGRES, description="Target database technology")
    network_exposure: NetworkExposure = Field(default=NetworkExposure.LOAD_BALANCER, description="Kubernetes service exposure")
    monitoring: MonitoringPreference = Field(default=MonitoringPreference.PROMETHEUS_GRAFANA, description="Observability stack")
    raw_request: str = Field(default="", description="Original natural-language requirement")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Parser confidence")
    notes: Optional[str] = None

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\-]", "-", v.lower().strip())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")
        return cleaned or "infra-service"


class ParseResult(BaseModel):
    """Result returned by the requirement parser endpoint."""
    success: bool
    spec: Optional[InfrastructureSpec] = None
    missing_fields: List[str] = Field(default_factory=list)
    invalid_fields: List[str] = Field(default_factory=list)
    clarifications_needed: List[str] = Field(default_factory=list)
    raw_llm_output: Optional[str] = None
    parser_used: str = "rule-based"


SYSTEM_PROMPT = """You are a Principal Cloud Infrastructure Architect & Platform Engineer.
Your task is to parse a natural-language infrastructure requirement and output ONLY a valid JSON object matching the specification schema.

Valid schema options:
- service_name: string (e.g. "payment-api", "auth-service")
- service_type: "web-api" | "frontend-spa" | "worker" | "full-stack"
- environment: "development" | "staging" | "production"
- replica_count: integer between 1 and 20
- database: "none" | "postgres" | "mysql" | "mongodb" | "redis"
- network_exposure: "cluster-ip" | "node-port" | "load-balancer"
- monitoring: "prometheus-grafana" | "basic" | "none"

Return ONLY the raw JSON object. Do not enclose in markdown code fences. Do not output explanatory text.
Example:
{"service_name": "order-api", "service_type": "web-api", "environment": "production", "replica_count": 3, "database": "postgres", "network_exposure": "load-balancer", "monitoring": "prometheus-grafana"}
"""


def build_llm_prompt(user_request: str) -> str:
    """Constructs prompt for LLM models."""
    return f"{SYSTEM_PROMPT}\n\nNatural Language Requirement:\n\"{user_request.strip()}\"\n\nJSON Output:"


def extract_json_from_text(text: str) -> Optional[dict]:
    """Safely extracts a JSON dictionary from raw model output."""
    if not text:
        return None
    cleaned = text.strip()
    
    # Remove markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        # Match outermost curly braces
        json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def rule_based_parse(prompt: str) -> Dict[str, Any]:
    """
    Deterministic rule-based extractor using regex and NLP keyword analysis.
    Provides offline capability and guaranteed fallback when LLM is unavailable.
    """
    text = prompt.lower()
    data: Dict[str, Any] = {}

    # 1. Service Type Detection
    if any(k in text for k in ["worker", "consumer", "celery", "queue", "batch", "cron", "background"]):
        data["service_type"] = ServiceType.WORKER.value
    elif any(k in text for k in ["full-stack", "fullstack", "both frontend and backend"]):
        data["service_type"] = ServiceType.FULL_STACK.value
    elif any(k in text for k in ["frontend", "react", "vue", "angular", "spa", "client app", "web app", "dashboard"]):
        data["service_type"] = ServiceType.FRONTEND_SPA.value
    elif any(k in text for k in ["api", "rest", "fastapi", "flask", "django", "backend", "microservice", "service"]):
        data["service_type"] = ServiceType.WEB_API.value

    # 2. Environment Detection
    if any(k in text for k in ["prod", "production", "live"]):
        data["environment"] = Environment.PRODUCTION.value
    elif any(k in text for k in ["stage", "staging", "uat", "preprod"]):
        data["environment"] = Environment.STAGING.value
    elif any(k in text for k in ["dev", "development", "local", "test"]):
        data["environment"] = Environment.DEVELOPMENT.value

    # 3. Replica Count Detection
    replica_match = re.search(r"(\d+)\s*(?:replicas|replica|instances|pods|nodes|copies)", text)
    if replica_match:
        data["replica_count"] = int(replica_match.group(1))
    elif "high-availability" in text or "ha" in text.split() or "high availability" in text:
        data["replica_count"] = 3
    elif data.get("environment") == Environment.PRODUCTION.value:
        data["replica_count"] = 3
    elif data.get("environment") == Environment.DEVELOPMENT.value:
        data["replica_count"] = 1

    # 4. Database Detection
    if any(k in text for k in ["postgres", "postgresql", "psql", "pg"]):
        data["database"] = DatabaseType.POSTGRES.value
    elif any(k in text for k in ["mysql", "mariadb"]):
        data["database"] = DatabaseType.MYSQL.value
    elif any(k in text for k in ["mongo", "mongodb"]):
        data["database"] = DatabaseType.MONGODB.value
    elif any(k in text for k in ["redis", "cache", "key-value"]):
        data["database"] = DatabaseType.REDIS.value
    elif any(k in text for k in ["no db", "no database", "stateless", "without database"]):
        data["database"] = DatabaseType.NONE.value

    # 5. Network Exposure Detection
    if any(k in text for k in ["ingress", "loadbalancer", "load balancer", "public", "external", "internet"]):
        data["network_exposure"] = NetworkExposure.LOAD_BALANCER.value
    elif any(k in text for k in ["nodeport", "node-port"]):
        data["network_exposure"] = NetworkExposure.NODE_PORT.value
    elif any(k in text for k in ["internal", "private", "clusterip", "cluster-ip"]):
        data["network_exposure"] = NetworkExposure.CLUSTER_IP.value

    # 6. Monitoring Detection
    if any(k in text for k in ["prometheus", "grafana", "metrics", "observability"]):
        data["monitoring"] = MonitoringPreference.PROMETHEUS_GRAFANA.value
    elif any(k in text for k in ["health check", "healthcheck", "ping", "basic monitoring"]):
        data["monitoring"] = MonitoringPreference.BASIC.value
    elif any(k in text for k in ["no monitoring", "without monitoring"]):
        data["monitoring"] = MonitoringPreference.NONE.value

    # 7. Service Name Extraction
    name_match = re.search(r"(?:named|called|service\s+name(?:\s*is)?(?:\s*:)?)\s*([a-zA-Z0-9_\-]+)", text)
    if name_match:
        data["service_name"] = name_match.group(1)
    else:
        # Look for leading words like "payment-gateway", "user-service"
        slug_match = re.search(r"\b([a-zA-Z0-9\-]+-(?:api|service|worker|app))\b", text)
        if slug_match:
            data["service_name"] = slug_match.group(1)

    return data


def validate_and_build_spec(data: Dict[str, Any], raw_request: str, parser_used: str = "rule-based") -> ParseResult:
    """
    Validates extracted parameters, detects missing/invalid fields,
    adds clarification notices, and constructs the InfrastructureSpec.
    """
    missing_fields: List[str] = []
    invalid_fields: List[str] = []
    clarifications: List[str] = []

    # Check for empty or trivial request
    if len(raw_request.strip()) < 4 or re.match(r"^[\s\W]+$", raw_request):
        return ParseResult(
            success=False,
            missing_fields=["service_type", "environment"],
            clarifications_needed=["The infrastructure requirement provided is too brief or ambiguous. Please describe the service type, environment, and resources needed."],
            parser_used=parser_used
        )

    # Validate service_type
    raw_st = data.get("service_type")
    service_type = None
    if raw_st:
        try:
            service_type = ServiceType(raw_st)
        except ValueError:
            invalid_fields.append("service_type")
    else:
        missing_fields.append("service_type")
        clarifications.append("Service type was not specified; defaulting to Web API (FastAPI).")
        service_type = ServiceType.WEB_API

    # Validate environment
    raw_env = data.get("environment")
    environment = None
    if raw_env:
        try:
            environment = Environment(raw_env)
        except ValueError:
            invalid_fields.append("environment")
    else:
        missing_fields.append("environment")
        clarifications.append("Target environment was not specified; defaulting to Production.")
        environment = Environment.PRODUCTION

    # Validate replica_count
    raw_rep = data.get("replica_count")
    replica_count = 2
    if raw_rep is not None:
        try:
            val = int(raw_rep)
            if 1 <= val <= 20:
                replica_count = val
            else:
                invalid_fields.append("replica_count")
                clarifications.append(f"Requested replica count ({val}) exceeds allowed policy range (1-20). Clamped to safe boundary.")
                replica_count = max(1, min(20, val))
        except (ValueError, TypeError):
            invalid_fields.append("replica_count")
    else:
        replica_count = 3 if environment == Environment.PRODUCTION else 1

    # Production safety notice
    if environment == Environment.PRODUCTION and replica_count < 2:
        clarifications.append("Warning: Production services typically require at least 2 replicas to ensure high availability and zero-downtime rolling updates.")

    # Validate database
    raw_db = data.get("database")
    database = DatabaseType.NONE
    if raw_db:
        try:
            database = DatabaseType(raw_db)
        except ValueError:
            invalid_fields.append("database")
    else:
        # If web-api or full-stack, default to postgres; worker to redis
        if service_type in [ServiceType.WEB_API, ServiceType.FULL_STACK]:
            database = DatabaseType.POSTGRES
        elif service_type == ServiceType.WORKER:
            database = DatabaseType.REDIS

    # Validate network exposure
    raw_exp = data.get("network_exposure")
    network_exposure = NetworkExposure.CLUSTER_IP
    if raw_exp:
        try:
            network_exposure = NetworkExposure(raw_exp)
        except ValueError:
            invalid_fields.append("network_exposure")
    else:
        if service_type in [ServiceType.WEB_API, ServiceType.FRONTEND_SPA, ServiceType.FULL_STACK]:
            network_exposure = NetworkExposure.LOAD_BALANCER
        else:
            network_exposure = NetworkExposure.CLUSTER_IP

    # Exposure safety warning
    if database != DatabaseType.NONE and network_exposure == NetworkExposure.LOAD_BALANCER and service_type == ServiceType.WORKER:
        clarifications.append("Caution: Public LoadBalancer exposure on a background worker with direct database access may violate network segregation policy.")

    # Validate monitoring
    raw_mon = data.get("monitoring")
    monitoring = MonitoringPreference.PROMETHEUS_GRAFANA
    if raw_mon:
        try:
            monitoring = MonitoringPreference(raw_mon)
        except ValueError:
            invalid_fields.append("monitoring")
    else:
        monitoring = MonitoringPreference.PROMETHEUS_GRAFANA if environment == Environment.PRODUCTION else MonitoringPreference.BASIC

    service_name = data.get("service_name") or "infra-service"

    # Confidence calculation
    confidence = 1.0
    if missing_fields:
        confidence -= 0.15 * len(missing_fields)
    if invalid_fields:
        confidence -= 0.20 * len(invalid_fields)
    confidence = max(0.2, min(1.0, confidence))

    spec = InfrastructureSpec(
        service_name=service_name,
        service_type=service_type,
        environment=environment,
        replica_count=replica_count,
        database=database,
        network_exposure=network_exposure,
        monitoring=monitoring,
        raw_request=raw_request,
        confidence_score=round(confidence, 2)
    )

    return ParseResult(
        success=len(invalid_fields) == 0,
        spec=spec,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
        clarifications_needed=clarifications,
        parser_used=parser_used
    )


async def parse_infrastructure_requirements(
    prompt: str,
    ai_provider: Optional[Any] = None,
    preferred_model: str = "llama3"
) -> ParseResult:
    """
    Main entry point for parsing infrastructure requirements.
    Queries the AI provider if available; otherwise employs deterministic rule parsing.
    """
    raw_output: Optional[str] = None
    parsed_data: Optional[Dict[str, Any]] = None
    parser_used = "rule-based"

    # Attempt AI inference if provider is configured and not purely rule-based
    if ai_provider is not None:
        provider_name = getattr(ai_provider, "get_name", lambda: "AI Provider")()
        if "rule-based" not in provider_name.lower():
            try:
                llm_prompt = build_llm_prompt(prompt)
                raw_output = await ai_provider.analyze(llm_prompt)
                if raw_output:
                    parsed_data = extract_json_from_text(raw_output)
                    if parsed_data:
                        parser_used = getattr(ai_provider, "model", "ai-provider")
            except Exception as e:
                # LLM execution failed; proceed to rule-based fallback
                raw_output = f"LLM error: {str(e)}"

    # If LLM didn't return valid dict, execute deterministic rule extraction
    if not parsed_data:
        parsed_data = rule_based_parse(prompt)
        parser_used = "rule-based"

    result = validate_and_build_spec(parsed_data, prompt, parser_used=parser_used)
    result.raw_llm_output = raw_output
    return result
