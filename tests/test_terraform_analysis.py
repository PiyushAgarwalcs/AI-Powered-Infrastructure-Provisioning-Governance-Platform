"""
Terraform plan parsing and blast-radius tests cover:
  - Plan JSON parsing from realistic and synthetic fixtures
  - Resource change classification (action, category, is_destructive)
  - Dependency edge extraction (explicit + implicit)
  - Blast-radius score and level determination
  - Warning generation for destructive/high-risk changes
  - Mock plan generation from HCL strings
  - API endpoint handlers for /api/terraform/analyze and /api/terraform/blast-radius
  - allow-list enforcement (apply never permitted)
  - Deterministic plan_hash stability
"""
import json
import hashlib
import pytest

from infra_platform.infrastructure.terraform_runner import (
    ChangeAction, BlastLevel, ResourceCategory,
    ResourceChange, DependencyEdge, BlastRadiusResult,
    TerraformExecutionResult,
    _infer_action, _classify_resource_type, _parse_provider,
    _extract_affected_attributes, _count_downstream,
    parse_plan_json, calculate_blast_radius,
    build_mock_plan_json, run_terraform_plan_analysis,
    blast_radius_to_dict, execution_result_to_dict,
    _SAFE_TERRAFORM_COMMANDS, _run_terraform_command,
)
from main import analyze_terraform_plan, get_blast_radius_for_spec
from infra_platform.infrastructure.requirement_parser import (
    InfrastructureSpec, ServiceType, Environment,
    DatabaseType, NetworkExposure, MonitoringPreference
)
from infra_platform.infrastructure.generators import generate_terraform_for_spec


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_sync(coro):
    """Executes a coroutine synchronously without event loop socketpair overhead."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


def make_resource_change_raw(
    res_type: str,
    res_name: str,
    actions: list,
    before: dict = None,
    after: dict = None,
) -> dict:
    """Helper to build a raw resource_change dict for plan JSON fixtures."""
    return {
        "address": f"{res_type}.{res_name}",
        "module_address": None,
        "type": res_type,
        "name": res_name,
        "provider_name": "registry.terraform.io/hashicorp/aws",
        "change": {
            "actions": actions,
            "before": before,
            "after": after,
            "after_unknown": {},
            "before_sensitive": {},
            "after_sensitive": {},
            "action_reason": None,
        },
    }


SAMPLE_PLAN_JSON: dict = {
    "format_version": "1.1",
    "terraform_version": "1.5.7",
    "variables": {},
    "resource_changes": [
        make_resource_change_raw(
            "aws_vpc", "main",
            actions=["create"],
            after={"cidr_block": "10.0.0.0/16", "enable_dns_hostnames": True},
        ),
        make_resource_change_raw(
            "aws_subnet", "public_1",
            actions=["create"],
            after={"cidr_block": "10.0.1.0/24", "vpc_id": "mock-vpc"},
        ),
        make_resource_change_raw(
            "aws_subnet", "public_2",
            actions=["create"],
            after={"cidr_block": "10.0.2.0/24", "vpc_id": "mock-vpc"},
        ),
        make_resource_change_raw(
            "aws_security_group", "app",
            actions=["create"],
            after={"name": "app-sg", "vpc_id": "mock-vpc"},
        ),
        make_resource_change_raw(
            "aws_security_group", "db",
            actions=["create"],
            after={"name": "db-sg", "vpc_id": "mock-vpc"},
        ),
        make_resource_change_raw(
            "aws_db_subnet_group", "main",
            actions=["create"],
            after={"name": "api-service-db-subnet"},
        ),
        make_resource_change_raw(
            "aws_ecr_repository", "app",
            actions=["create"],
            after={"name": "api-service", "image_tag_mutability": "MUTABLE"},
        ),
        make_resource_change_raw(
            "aws_db_instance", "postgres",
            actions=["create"],
            after={
                "engine": "postgres",
                "engine_version": "16.3",
                "instance_class": "db.t3.medium",
                "db_name": "api_service",
                "username": "pgadmin",
                "allocated_storage": 20,
            },
        ),
    ],
    "configuration": {
        "root_module": {
            "resources": []
        }
    },
}

DESTRUCTIVE_PLAN_JSON: dict = {
    "format_version": "1.1",
    "terraform_version": "1.5.7",
    "variables": {},
    "resource_changes": [
        make_resource_change_raw(
            "aws_db_instance", "postgres",
            actions=["delete"],
            before={
                "engine": "postgres",
                "instance_class": "db.t3.medium",
                "db_name": "prod_db",
                "allocated_storage": 100,
            },
            after=None,
        ),
        make_resource_change_raw(
            "aws_security_group", "app",
            actions=["delete"],
            before={"name": "prod-app-sg"},
            after=None,
        ),
        make_resource_change_raw(
            "aws_vpc", "main",
            actions=["no-op"],
            before={"cidr_block": "10.0.0.0/16"},
            after={"cidr_block": "10.0.0.0/16"},
        ),
    ],
    "configuration": {"root_module": {"resources": []}},
}

MODIFY_PLAN_JSON: dict = {
    "format_version": "1.1",
    "terraform_version": "1.5.7",
    "variables": {},
    "resource_changes": [
        make_resource_change_raw(
            "aws_db_instance", "postgres",
            actions=["update"],
            before={"instance_class": "db.t3.micro", "allocated_storage": 20},
            after={"instance_class": "db.t3.medium", "allocated_storage": 100},
        ),
        make_resource_change_raw(
            "aws_ecr_repository", "app",
            actions=["no-op"],
            before={"name": "api-service"},
            after={"name": "api-service"},
        ),
    ],
    "configuration": {"root_module": {"resources": []}},
}

REPLACE_PLAN_JSON: dict = {
    "format_version": "1.1",
    "terraform_version": "1.5.7",
    "variables": {},
    "resource_changes": [
        make_resource_change_raw(
            "aws_db_instance", "postgres",
            actions=["delete", "create"],
            before={"engine": "postgres", "engine_version": "14.0"},
            after={"engine": "postgres", "engine_version": "16.3"},
        ),
        make_resource_change_raw(
            "aws_security_group", "app",
            actions=["create"],
            after={"name": "app-sg-v2"},
        ),
    ],
    "configuration": {"root_module": {"resources": []}},
}


# ── 1. Action inference ───────────────────────────────────────────────────────

class TestActionInference:

    def test_create_maps_to_add(self):
        assert _infer_action(["create"]) == ChangeAction.ADD

    def test_delete_maps_to_destroy(self):
        assert _infer_action(["delete"]) == ChangeAction.DESTROY

    def test_update_maps_to_modify(self):
        assert _infer_action(["update"]) == ChangeAction.MODIFY

    def test_noop_maps_to_noop(self):
        assert _infer_action(["no-op"]) == ChangeAction.NO_OP

    def test_read_maps_to_read(self):
        assert _infer_action(["read"]) == ChangeAction.READ

    def test_delete_create_maps_to_replace(self):
        assert _infer_action(["delete", "create"]) == ChangeAction.REPLACE

    def test_empty_maps_to_noop(self):
        assert _infer_action([]) == ChangeAction.NO_OP


# ── 2. Resource classification ────────────────────────────────────────────────

class TestResourceClassification:

    def test_vpc_is_network(self):
        assert _classify_resource_type("aws_vpc") == ResourceCategory.NETWORK

    def test_subnet_is_network(self):
        assert _classify_resource_type("aws_subnet") == ResourceCategory.NETWORK

    def test_security_group_is_security(self):
        assert _classify_resource_type("aws_security_group") == ResourceCategory.SECURITY

    def test_db_instance_is_database(self):
        assert _classify_resource_type("aws_db_instance") == ResourceCategory.DATABASE

    def test_ecr_is_registry(self):
        assert _classify_resource_type("aws_ecr_repository") == ResourceCategory.REGISTRY

    def test_ec2_instance_is_compute(self):
        assert _classify_resource_type("aws_instance") == ResourceCategory.COMPUTE

    def test_s3_is_storage(self):
        assert _classify_resource_type("aws_s3_bucket") == ResourceCategory.STORAGE

    def test_iam_is_iam(self):
        assert _classify_resource_type("aws_iam_role") == ResourceCategory.IAM

    def test_cloudwatch_is_observability(self):
        assert _classify_resource_type("aws_cloudwatch_metric_alarm") == ResourceCategory.OBSERVABILITY

    def test_unknown_type(self):
        assert _classify_resource_type("custom_resource_type") == ResourceCategory.UNKNOWN

    def test_provider_extraction(self):
        assert _parse_provider("aws_vpc") == "aws"
        assert _parse_provider("google_compute_instance") == "google"


# ── 3. Affected attributes ────────────────────────────────────────────────────

class TestAffectedAttributes:

    def test_no_change_returns_empty(self):
        state = {"engine": "postgres", "size": 20}
        assert _extract_affected_attributes(state, state) == []

    def test_detects_changed_key(self):
        before = {"instance_class": "db.t3.micro", "allocated_storage": 20}
        after = {"instance_class": "db.t3.medium", "allocated_storage": 100}
        changed = _extract_affected_attributes(before, after)
        assert "instance_class" in changed
        assert "allocated_storage" in changed

    def test_detects_new_key(self):
        before = {"name": "test"}
        after = {"name": "test", "tags": {"Env": "prod"}}
        assert "tags" in _extract_affected_attributes(before, after)

    def test_none_states_return_empty(self):
        assert _extract_affected_attributes(None, None) == []
        assert _extract_affected_attributes(None, {"key": "val"}) == []


# ── 4. Plan JSON parsing ──────────────────────────────────────────────────────

class TestPlanJsonParsing:

    def test_parse_sample_plan_resource_count(self):
        changes, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        # 8 resources in fixture
        assert len(changes) == 8

    def test_parse_all_adds_in_sample(self):
        changes, _ = parse_plan_json(SAMPLE_PLAN_JSON)
        assert all(rc.action == ChangeAction.ADD for rc in changes)

    def test_parse_vpc_category(self):
        changes, _ = parse_plan_json(SAMPLE_PLAN_JSON)
        vpc = next(rc for rc in changes if rc.resource_type == "aws_vpc")
        assert vpc.category == ResourceCategory.NETWORK
        assert not vpc.is_destructive

    def test_parse_db_instance_category(self):
        changes, _ = parse_plan_json(SAMPLE_PLAN_JSON)
        db = next(rc for rc in changes if rc.resource_type == "aws_db_instance")
        assert db.category == ResourceCategory.DATABASE

    def test_parse_destructive_plan(self):
        changes, _ = parse_plan_json(DESTRUCTIVE_PLAN_JSON)
        destroys = [rc for rc in changes if rc.action == ChangeAction.DESTROY]
        assert len(destroys) == 2  # db_instance and security_group
        no_ops = [rc for rc in changes if rc.action == ChangeAction.NO_OP]
        assert len(no_ops) == 1

    def test_parse_replace_action(self):
        changes, _ = parse_plan_json(REPLACE_PLAN_JSON)
        replaces = [rc for rc in changes if rc.action == ChangeAction.REPLACE]
        assert len(replaces) == 1
        assert replaces[0].is_destructive is True
        assert replaces[0].resource_type == "aws_db_instance"

    def test_parse_modify_detects_affected_attrs(self):
        changes, _ = parse_plan_json(MODIFY_PLAN_JSON)
        db_modify = next(rc for rc in changes if rc.action == ChangeAction.MODIFY)
        assert "instance_class" in db_modify.affected_attributes
        assert "allocated_storage" in db_modify.affected_attributes

    def test_implicit_dependencies_added_for_rds(self):
        """RDS should have implicit edges to security_group and db_subnet_group."""
        _, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        db_edges = [e for e in edges if e.source == "aws_db_instance.postgres"]
        targets = {e.target for e in db_edges}
        # Should depend on at least one security group
        assert any("aws_security_group" in t for t in targets)

    def test_empty_plan_returns_empty_lists(self):
        empty = {"format_version": "1.1", "resource_changes": []}
        changes, edges = parse_plan_json(empty)
        assert changes == []


# ── 5. Downstream dependency counting ────────────────────────────────────────

class TestDownstreamCounting:

    def test_no_dependents_returns_zero(self):
        # An isolated resource with no edges at all has zero downstream dependents.
        edges = []
        assert _count_downstream("aws_vpc.main", edges) == 0

    def test_target_has_downstream_when_source_depends_on_it(self):
        # Edge: db depends on vpc → vpc has 1 downstream (db)
        edges = [DependencyEdge(source="aws_db_instance.postgres", target="aws_vpc.main")]
        assert _count_downstream("aws_vpc.main", edges) == 1

    def test_direct_downstream(self):
        edges = [DependencyEdge(source="aws_db_instance.postgres", target="aws_vpc.main")]
        # postgres depends on vpc → vpc has 1 downstream
        assert _count_downstream("aws_vpc.main", edges) == 1

    def test_transitive_downstream(self):
        edges = [
            DependencyEdge(source="aws_security_group.db", target="aws_vpc.main"),
            DependencyEdge(source="aws_db_instance.postgres", target="aws_security_group.db"),
        ]
        # vpc → sg → db — transitively 2 dependents
        assert _count_downstream("aws_vpc.main", edges) == 2


# ── 6. Blast-radius calculation ───────────────────────────────────────────────

class TestBlastRadiusCalculation:

    def test_all_add_plan_is_low_or_medium(self):
        changes, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, SAMPLE_PLAN_JSON)
        assert result.level in (BlastLevel.LOW, BlastLevel.MEDIUM)
        assert result.score >= 0
        assert result.adds == 8
        assert result.destroys == 0

    def test_destructive_plan_raises_to_high_or_critical(self):
        changes, edges = parse_plan_json(DESTRUCTIVE_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, DESTRUCTIVE_PLAN_JSON)
        assert result.level in (BlastLevel.HIGH, BlastLevel.CRITICAL)
        assert result.destroys == 2
        assert result.score >= 50

    def test_replace_plan_generates_warning(self):
        changes, edges = parse_plan_json(REPLACE_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, REPLACE_PLAN_JSON)
        # Should have a REPLACEMENT warning
        assert any("REPLACEMENT" in w or "replace" in w.lower() for w in result.warnings)
        assert result.replaces == 1

    def test_destructive_db_generates_data_risk_warning(self):
        changes, edges = parse_plan_json(DESTRUCTIVE_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, DESTRUCTIVE_PLAN_JSON)
        assert any("DATA RISK" in w for w in result.warnings)

    def test_no_op_plan_scores_zero(self):
        no_op_plan = {
            "format_version": "1.1",
            "resource_changes": [
                make_resource_change_raw(
                    "aws_vpc", "main",
                    actions=["no-op"],
                    before={"cidr_block": "10.0.0.0/16"},
                    after={"cidr_block": "10.0.0.0/16"},
                )
            ],
            "configuration": {"root_module": {"resources": []}},
        }
        changes, edges = parse_plan_json(no_op_plan)
        result = calculate_blast_radius(changes, edges, no_op_plan)
        assert result.score == 0
        assert result.level == BlastLevel.LOW
        assert result.destroys == 0

    def test_score_capped_at_100(self):
        # Manufacture 20 destroy actions on databases (each worth 25+15=40 points)
        many_destroys = {
            "format_version": "1.1",
            "resource_changes": [
                make_resource_change_raw(
                    "aws_db_instance", f"db_{i}",
                    actions=["delete"],
                    before={"engine": "postgres"},
                    after=None,
                )
                for i in range(20)
            ],
            "configuration": {"root_module": {"resources": []}},
        }
        changes, edges = parse_plan_json(many_destroys)
        result = calculate_blast_radius(changes, edges, many_destroys)
        assert result.score <= 100

    def test_modify_plan_level(self):
        changes, edges = parse_plan_json(MODIFY_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, MODIFY_PLAN_JSON)
        assert result.modifies == 1
        assert result.no_ops == 1
        assert result.score > 0

    def test_plan_hash_is_stable(self):
        """Same plan JSON must always produce the same plan_hash."""
        changes, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        r1 = calculate_blast_radius(changes, edges, SAMPLE_PLAN_JSON)
        r2 = calculate_blast_radius(changes, edges, SAMPLE_PLAN_JSON)
        assert r1.plan_hash == r2.plan_hash

    def test_plan_hash_differs_for_different_plans(self):
        c1, e1 = parse_plan_json(SAMPLE_PLAN_JSON)
        c2, e2 = parse_plan_json(DESTRUCTIVE_PLAN_JSON)
        r1 = calculate_blast_radius(c1, e1, SAMPLE_PLAN_JSON)
        r2 = calculate_blast_radius(c2, e2, DESTRUCTIVE_PLAN_JSON)
        assert r1.plan_hash != r2.plan_hash

    def test_summary_contains_key_info(self):
        changes, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, SAMPLE_PLAN_JSON)
        assert "8" in result.summary or "resource" in result.summary
        # Level appears uppercased in the summary string (e.g., "LOW", "HIGH")
        assert result.level.value.upper() in result.summary

    def test_affected_categories_populated(self):
        changes, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        result = calculate_blast_radius(changes, edges, SAMPLE_PLAN_JSON)
        assert len(result.affected_categories) > 0
        assert "network" in result.affected_categories or "database" in result.affected_categories


# ── 7. Mock plan generator ────────────────────────────────────────────────────

class TestMockPlanGenerator:

    def test_generates_plan_from_hcl_string(self):
        hcl = """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
resource "aws_db_instance" "postgres" {
  engine = "postgres"
}
"""
        plan = build_mock_plan_json(hcl, "test-svc")
        assert "resource_changes" in plan
        assert len(plan["resource_changes"]) == 2
        types = [rc["type"] for rc in plan["resource_changes"]]
        assert "aws_vpc" in types
        assert "aws_db_instance" in types

    def test_all_mock_actions_are_create(self):
        hcl = 'resource "aws_ecr_repository" "app" { name = "test" }'
        plan = build_mock_plan_json(hcl, "ecr-test")
        for rc in plan["resource_changes"]:
            assert rc["change"]["actions"] == ["create"]

    def test_mock_flag_is_set(self):
        plan = build_mock_plan_json('resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }')
        assert plan.get("_mock") is True

    def test_empty_hcl_returns_empty_changes(self):
        plan = build_mock_plan_json("# just a comment", "empty-svc")
        assert plan["resource_changes"] == []


# ── 8. Run analysis orchestrator ─────────────────────────────────────────────

class TestRunTerraformPlanAnalysis:

    @pytest.fixture
    def sample_hcl(self):
        """Realistic HCL matching the structure generated by generate_terraform_for_spec."""
        return """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
resource "aws_subnet" "public_1" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}
resource "aws_security_group" "app" {
  vpc_id = aws_vpc.main.id
}
resource "aws_security_group" "db" {
  vpc_id = aws_vpc.main.id
}
resource "aws_db_subnet_group" "main" {
  name = "api-service-db-subnet"
}
resource "aws_ecr_repository" "app" {
  name = "api-service-production"
}
resource "aws_db_instance" "postgres" {
  engine = "postgres"
  engine_version = "16.3"
  instance_class = "db.t3.medium"
}
"""

    def test_mock_analysis_success(self, sample_hcl):
        result = run_terraform_plan_analysis(sample_hcl, "api-service", use_cli=False)
        assert result.success is True
        assert result.blast_radius is not None
        assert result.blast_radius.score >= 0

    def test_mock_analysis_has_resource_changes(self, sample_hcl):
        result = run_terraform_plan_analysis(sample_hcl, "api-service", use_cli=False)
        assert result.blast_radius.total_changes == 7

    def test_mock_analysis_all_adds(self, sample_hcl):
        result = run_terraform_plan_analysis(sample_hcl, "api-service", use_cli=False)
        assert result.blast_radius.adds == 7
        assert result.blast_radius.destroys == 0

    def test_mock_analysis_detects_database_category(self, sample_hcl):
        result = run_terraform_plan_analysis(sample_hcl, "api-service", use_cli=False)
        cats = result.blast_radius.affected_categories
        assert "database" in cats

    def test_mock_analysis_has_plan_json(self, sample_hcl):
        result = run_terraform_plan_analysis(sample_hcl, "api-service", use_cli=False)
        assert result.plan_json is not None
        assert "resource_changes" in result.plan_json

    def test_no_apply_command_in_allowlist(self):
        """Verify terraform apply is NEVER in the allow-list."""
        assert "apply" not in _SAFE_TERRAFORM_COMMANDS

    def test_apply_raises_value_error(self):
        """Attempting to run apply via _run_terraform_command must raise ValueError."""
        with pytest.raises(ValueError, match="not permitted"):
            _run_terraform_command(["apply", "-auto-approve"], cwd=".", timeout=5)

    def test_destroy_raises_value_error(self):
        """Attempting to run destroy via _run_terraform_command must raise ValueError."""
        with pytest.raises(ValueError, match="not permitted"):
            _run_terraform_command(["destroy", "-auto-approve"], cwd=".", timeout=5)


# ── 9. Integration with spec-driven Terraform HCL ────────────────────────────

class TestSpecDrivenIntegration:

    @pytest.fixture
    def prod_spec(self):
        return InfrastructureSpec(
            service_name="payment-api",
            service_type=ServiceType.WEB_API,
            environment=Environment.PRODUCTION,
            replica_count=3,
            database=DatabaseType.POSTGRES,
            network_exposure=NetworkExposure.LOAD_BALANCER,
            monitoring=MonitoringPreference.PROMETHEUS_GRAFANA,
        )

    def test_spec_hcl_generates_valid_plan(self, prod_spec):
        """Generate Terraform HCL from spec and confirm blast-radius analysis succeeds."""
        hcl = generate_terraform_for_spec(prod_spec)
        result = run_terraform_plan_analysis(hcl, prod_spec.service_name, use_cli=False)
        assert result.success is True
        assert result.blast_radius is not None
        assert result.blast_radius.total_changes >= 1

    def test_spec_hcl_contains_expected_resources(self, prod_spec):
        hcl = generate_terraform_for_spec(prod_spec)
        result = run_terraform_plan_analysis(hcl, prod_spec.service_name, use_cli=False)
        types = [rc.resource_type for rc in result.blast_radius.resource_changes]
        assert "aws_vpc" in types
        assert "aws_db_instance" in types
        assert "aws_ecr_repository" in types

    def test_no_database_spec_omits_rds(self):
        spec = InfrastructureSpec(
            service_name="stateless-api",
            service_type=ServiceType.WEB_API,
            environment=Environment.DEVELOPMENT,
            replica_count=1,
            database=DatabaseType.NONE,
            network_exposure=NetworkExposure.CLUSTER_IP,
            monitoring=MonitoringPreference.NONE,
        )
        hcl = generate_terraform_for_spec(spec)
        result = run_terraform_plan_analysis(hcl, spec.service_name, use_cli=False)
        types = [rc.resource_type for rc in result.blast_radius.resource_changes]
        assert "aws_db_instance" not in types


# ── 10. Serialization helpers ─────────────────────────────────────────────────

class TestSerialization:

    def test_blast_radius_to_dict_has_required_keys(self):
        changes, edges = parse_plan_json(SAMPLE_PLAN_JSON)
        blast = calculate_blast_radius(changes, edges, SAMPLE_PLAN_JSON)
        d = blast_radius_to_dict(blast)
        for key in ("plan_id", "score", "level", "total_changes", "adds", "destroys",
                    "modifies", "replaces", "warnings", "summary", "plan_hash",
                    "resource_changes", "dependency_edges", "affected_categories"):
            assert key in d, f"Missing key: {key}"

    def test_blast_radius_to_dict_is_json_serializable(self):
        changes, edges = parse_plan_json(DESTRUCTIVE_PLAN_JSON)
        blast = calculate_blast_radius(changes, edges, DESTRUCTIVE_PLAN_JSON)
        d = blast_radius_to_dict(blast)
        # Should not raise
        encoded = json.dumps(d)
        decoded = json.loads(encoded)
        assert decoded["level"] in ("low", "medium", "high", "critical")

    def test_execution_result_to_dict_structure(self):
        hcl = 'resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }'
        result = run_terraform_plan_analysis(hcl, use_cli=False)
        d = execution_result_to_dict(result)
        assert "success" in d
        assert "blast_radius" in d
        assert d["blast_radius"] is not None
        assert "command" in d


# ── 11. API endpoint handlers ─────────────────────────────────────────────────

class TestApiEndpoints:

    @pytest.fixture
    def sample_hcl(self):
        return """
resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
resource "aws_db_instance" "postgres" { engine = "postgres" }
resource "aws_ecr_repository" "app" { name = "test-api" }
"""

    def test_analyze_terraform_plan_endpoint(self, sample_hcl):
        """Test POST /api/terraform/analyze endpoint handler."""
        from main import TerraformAnalyzeRequest
        req = TerraformAnalyzeRequest(
            terraform_hcl=sample_hcl,
            service_name="test-api",
            use_cli=False,
        )
        response = run_sync(analyze_terraform_plan(req))
        assert response["success"] is True
        assert "blast_radius" in response
        assert response["blast_radius"]["total_changes"] == 3

    def test_analyze_endpoint_returns_level(self, sample_hcl):
        from main import TerraformAnalyzeRequest
        req = TerraformAnalyzeRequest(
            terraform_hcl=sample_hcl,
            service_name="test-api",
            use_cli=False,
        )
        response = run_sync(analyze_terraform_plan(req))
        assert response["blast_radius"]["level"] in ("low", "medium", "high", "critical")

    def test_analyze_endpoint_includes_warnings(self):
        """Destructive plan should trigger warnings in API response."""
        destructive_hcl = """
resource "aws_db_instance" "postgres" { engine = "postgres" }
"""
        # Build a plan with destroy action by calling analysis on explicit plan JSON
        from main import TerraformPlanRequest
        req = TerraformPlanRequest(
            plan_json=DESTRUCTIVE_PLAN_JSON,
            service_name="prod-api",
        )
        response = run_sync(get_blast_radius_for_spec(req))
        assert response["success"] is True
        assert len(response["blast_radius"]["warnings"]) > 0

    def test_blast_radius_endpoint_for_spec(self):
        """Test POST /api/terraform/blast-radius with explicit plan JSON."""
        from main import TerraformPlanRequest
        req = TerraformPlanRequest(
            plan_json=REPLACE_PLAN_JSON,
            service_name="replace-svc",
        )
        response = run_sync(get_blast_radius_for_spec(req))
        assert response["success"] is True
        br = response["blast_radius"]
        assert br["replaces"] == 1
        assert any("REPLACEMENT" in w or "replace" in w.lower() for w in br["warnings"])
