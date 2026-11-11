"""
Terraform Plan Runner & Blast-Radius Analyzer
Implements controlled Terraform execution (with optional CLI or mock fallback),
plan JSON parsing, resource change classification, dependency extraction,
and deterministic blast-radius scoring.

SAFETY CONTRACT:
- Never invokes `terraform apply` automatically.
- All execution is behind an explicit allow-list of safe subcommands.
- Generated plans are never applied without an explicit, separate human approval step.
"""

import json
import os
import re
import subprocess
import tempfile
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


# ── Enumerations ─────────────────────────────────────────────────────────────

class ChangeAction(str, Enum):
    """Terraform resource-level change classification."""
    ADD = "add"
    MODIFY = "modify"
    DESTROY = "destroy"
    NO_OP = "no-op"
    REPLACE = "replace"   # destroy-then-create or create-then-destroy
    READ = "read"


class BlastLevel(str, Enum):
    """Deterministic blast-radius severity tier."""
    CRITICAL = "critical"   # Score >= 80  — destructive, production, or many dependents
    HIGH = "high"           # Score 50-79  — significant modification or cross-layer impact
    MEDIUM = "medium"       # Score 25-49  — additive with moderate reach
    LOW = "low"             # Score 0-24   — purely additive, isolated changes


class ResourceCategory(str, Enum):
    """High-level infrastructure layer for a resource."""
    NETWORK = "network"
    COMPUTE = "compute"
    DATABASE = "database"
    SECURITY = "security"
    STORAGE = "storage"
    IAM = "iam"
    OBSERVABILITY = "observability"
    REGISTRY = "registry"
    UNKNOWN = "unknown"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ResourceChange:
    """Represents one resource's planned change from a Terraform plan."""
    address: str
    module_address: Optional[str]
    resource_type: str
    resource_name: str
    provider: str
    action: ChangeAction
    before: Optional[Dict[str, Any]]
    after: Optional[Dict[str, Any]]
    action_reason: Optional[str]
    # Computed by classifier
    category: ResourceCategory = ResourceCategory.UNKNOWN
    is_destructive: bool = False
    affected_attributes: List[str] = field(default_factory=list)
    replacement_forced_by: List[str] = field(default_factory=list)


@dataclass
class DependencyEdge:
    """Directed dependency between two resources."""
    source: str
    target: str


@dataclass
class BlastRadiusResult:
    """Complete blast-radius analysis result for a Terraform plan."""
    plan_id: str
    score: int                                    # 0–100 deterministic score
    level: BlastLevel
    total_changes: int
    adds: int
    modifies: int
    destroys: int
    replaces: int
    no_ops: int
    resource_changes: List[ResourceChange]
    affected_categories: List[str]
    dependency_edges: List[DependencyEdge]
    warnings: List[str]
    summary: str
    plan_hash: str                                # SHA-256 of normalized plan JSON
    created_at: float = field(default_factory=time.time)


@dataclass
class TerraformExecutionResult:
    """Result of a controlled Terraform CLI or mock execution."""
    success: bool
    command: str
    stdout: str
    stderr: str
    return_code: int
    plan_json: Optional[Dict[str, Any]] = None
    blast_radius: Optional[BlastRadiusResult] = None
    error: Optional[str] = None


# ── Resource Classifier ───────────────────────────────────────────────────────

# Mapping from Terraform resource type prefix → ResourceCategory
_CATEGORY_MAP: Dict[str, ResourceCategory] = {
    "aws_vpc":                   ResourceCategory.NETWORK,
    "aws_subnet":                ResourceCategory.NETWORK,
    "aws_internet_gateway":      ResourceCategory.NETWORK,
    "aws_route_table":           ResourceCategory.NETWORK,
    "aws_route":                 ResourceCategory.NETWORK,
    "aws_security_group":        ResourceCategory.SECURITY,
    "aws_security_group_rule":   ResourceCategory.SECURITY,
    "aws_iam":                   ResourceCategory.IAM,
    "aws_db":                    ResourceCategory.DATABASE,
    "aws_rds":                   ResourceCategory.DATABASE,
    "aws_docdb":                 ResourceCategory.DATABASE,
    "aws_elasticache":           ResourceCategory.DATABASE,
    "aws_ec2":                   ResourceCategory.COMPUTE,
    "aws_instance":              ResourceCategory.COMPUTE,
    "aws_launch_template":       ResourceCategory.COMPUTE,
    "aws_autoscaling":           ResourceCategory.COMPUTE,
    "aws_eks":                   ResourceCategory.COMPUTE,
    "aws_ecs":                   ResourceCategory.COMPUTE,
    "aws_lambda":                ResourceCategory.COMPUTE,
    "aws_s3":                    ResourceCategory.STORAGE,
    "aws_ebs":                   ResourceCategory.STORAGE,
    "aws_efs":                   ResourceCategory.STORAGE,
    "aws_ecr":                   ResourceCategory.REGISTRY,
    "aws_cloudwatch":            ResourceCategory.OBSERVABILITY,
    "aws_sns":                   ResourceCategory.OBSERVABILITY,
    "aws_sqs":                   ResourceCategory.OBSERVABILITY,
    "aws_lb":                    ResourceCategory.NETWORK,
    "aws_alb":                   ResourceCategory.NETWORK,
    "aws_elb":                   ResourceCategory.NETWORK,
    "aws_cloudfront":            ResourceCategory.NETWORK,
    "aws_route53":               ResourceCategory.NETWORK,
    "aws_acm":                   ResourceCategory.SECURITY,
    "aws_kms":                   ResourceCategory.SECURITY,
    "aws_waf":                   ResourceCategory.SECURITY,
    "aws_secretsmanager":        ResourceCategory.SECURITY,
    "aws_ssm":                   ResourceCategory.SECURITY,
}

# Attributes whose modification forces replacement (destructive by nature)
_REPLACEMENT_SENSITIVE_ATTRS = {
    "engine", "engine_version", "instance_class", "db_name", "username",
    "cidr_block", "availability_zone", "vpc_id", "subnet_id",
    "identifier", "cluster_identifier", "name", "bucket",
    "image_tag_mutability", "image_scanning_configuration",
}

# Score weights per change action (base points per resource)
_ACTION_WEIGHTS: Dict[ChangeAction, int] = {
    ChangeAction.DESTROY:  25,
    ChangeAction.REPLACE:  20,
    ChangeAction.MODIFY:    8,
    ChangeAction.ADD:       3,
    ChangeAction.READ:      0,
    ChangeAction.NO_OP:     0,
}

# Extra score penalties per resource category for destructive operations
_CATEGORY_PENALTIES: Dict[ResourceCategory, int] = {
    ResourceCategory.DATABASE:      15,
    ResourceCategory.NETWORK:       10,
    ResourceCategory.SECURITY:       8,
    ResourceCategory.IAM:            8,
    ResourceCategory.COMPUTE:        5,
    ResourceCategory.STORAGE:        5,
    ResourceCategory.REGISTRY:       3,
    ResourceCategory.OBSERVABILITY:  2,
    ResourceCategory.UNKNOWN:        0,
}


def _classify_resource_type(resource_type: str) -> ResourceCategory:
    """Map a Terraform resource type string to a ResourceCategory."""
    for prefix, category in _CATEGORY_MAP.items():
        if resource_type.startswith(prefix):
            return category
    return ResourceCategory.UNKNOWN


def _parse_provider(resource_type: str) -> str:
    """Extract provider name from resource type (e.g. 'aws' from 'aws_vpc')."""
    parts = resource_type.split("_", 1)
    return parts[0] if parts else "unknown"


def _extract_affected_attributes(before: Optional[Dict], after: Optional[Dict]) -> List[str]:
    """Return list of attribute keys that changed between before and after states."""
    if not before or not after:
        return []
    changed = []
    all_keys = set(before.keys()) | set(after.keys())
    for key in sorted(all_keys):
        b_val = before.get(key)
        a_val = after.get(key)
        if b_val != a_val:
            changed.append(key)
    return changed


def _infer_action(actions: List[str]) -> ChangeAction:
    """Normalize Terraform action array to a ChangeAction enum value."""
    if not actions:
        return ChangeAction.NO_OP
    s = set(actions)
    if s == {"no-op"}:
        return ChangeAction.NO_OP
    if s == {"read"}:
        return ChangeAction.READ
    if s == {"create"}:
        return ChangeAction.ADD
    if s == {"delete"}:
        return ChangeAction.DESTROY
    if s == {"update"}:
        return ChangeAction.MODIFY
    if "create" in s and "delete" in s:
        return ChangeAction.REPLACE
    # Fallback: treat any set containing "delete" as destructive
    if "delete" in s:
        return ChangeAction.DESTROY
    if "create" in s:
        return ChangeAction.ADD
    return ChangeAction.MODIFY


# ── Plan JSON Parser ──────────────────────────────────────────────────────────

def parse_plan_json(plan_json: Dict[str, Any]) -> Tuple[List[ResourceChange], List[DependencyEdge]]:
    """
    Parse a Terraform plan JSON object (from `terraform show -json`)
    into ResourceChange and DependencyEdge lists.

    Supports both Terraform >= 0.13 format (resource_changes key)
    and minimal synthetic test fixtures.
    """
    resource_changes: List[ResourceChange] = []
    dependency_edges: List[DependencyEdge] = []

    raw_changes = plan_json.get("resource_changes", [])
    if not isinstance(raw_changes, list):
        raw_changes = []

    # Build dependency map from configuration block if present
    config_resources = (
        plan_json
        .get("configuration", {})
        .get("root_module", {})
        .get("resources", [])
    )
    dep_map: Dict[str, List[str]] = {}
    for cfg_res in config_resources:
        addr = cfg_res.get("address", "")
        deps = cfg_res.get("expressions", {})
        # Terraform stores references as list of strings inside expression values
        all_refs: List[str] = []
        for expr_val in deps.values():
            if isinstance(expr_val, dict):
                for ref in expr_val.get("references", []):
                    if "." in ref and not ref.startswith("var."):
                        all_refs.append(ref)
        if all_refs:
            dep_map[addr] = all_refs

    # Parse resource_changes
    for raw in raw_changes:
        if not isinstance(raw, dict):
            continue

        address = raw.get("address", "")
        module_address = raw.get("module_address")
        resource_type = raw.get("type", "")
        resource_name = raw.get("name", "")

        change_block = raw.get("change", {})
        if not isinstance(change_block, dict):
            change_block = {}

        actions = change_block.get("actions", ["no-op"])
        before = change_block.get("before")
        after = change_block.get("after")
        action_reason = change_block.get("action_reason")

        # Collect replacement-forcing attributes from before_sensitive / after_unknown
        replacement_forced_by: List[str] = []
        before_sensitive = change_block.get("before_sensitive", {})
        if isinstance(before_sensitive, dict):
            replacement_forced_by = [
                k for k, v in before_sensitive.items()
                if v is True and k in _REPLACEMENT_SENSITIVE_ATTRS
            ]

        action = _infer_action(actions)
        category = _classify_resource_type(resource_type)
        provider = _parse_provider(resource_type)
        is_destructive = action in (ChangeAction.DESTROY, ChangeAction.REPLACE)
        affected_attrs = _extract_affected_attributes(
            before if isinstance(before, dict) else None,
            after if isinstance(after, dict) else None,
        )

        rc = ResourceChange(
            address=address,
            module_address=module_address,
            resource_type=resource_type,
            resource_name=resource_name,
            provider=provider,
            action=action,
            before=before if isinstance(before, dict) else None,
            after=after if isinstance(after, dict) else None,
            action_reason=action_reason,
            category=category,
            is_destructive=is_destructive,
            affected_attributes=affected_attrs,
            replacement_forced_by=replacement_forced_by,
        )
        resource_changes.append(rc)

    # Build dependency edges from both dep_map and plan prior_state references
    for src_addr, deps in dep_map.items():
        for dep in deps:
            # Normalize dep reference to its resource address
            # e.g. "aws_security_group.app.id" → "aws_security_group.app"
            parts = dep.split(".")
            if len(parts) >= 2:
                target_addr = ".".join(parts[:2])
                if target_addr != src_addr:
                    dependency_edges.append(DependencyEdge(source=src_addr, target=target_addr))

    # Also derive implicit edges from affected resources that share type prefixes with others
    # (e.g., RDS depending on DB subnet group and security group)
    _infer_implicit_dependencies(resource_changes, dependency_edges)

    return resource_changes, dependency_edges


def _infer_implicit_dependencies(
    changes: List[ResourceChange],
    edges: List[DependencyEdge]
) -> None:
    """
    Add well-known implicit AWS dependency edges not always present
    in Terraform plan configuration expressions.
    """
    existing = {(e.source, e.target) for e in edges}
    addresses_by_type: Dict[str, List[str]] = {}
    for rc in changes:
        addresses_by_type.setdefault(rc.resource_type, []).append(rc.address)

    # Pattern: RDS/DocDB instance depends on DB subnet group and security groups
    db_instance_types = ["aws_db_instance", "aws_docdb_cluster"]
    for db_type in db_instance_types:
        for db_addr in addresses_by_type.get(db_type, []):
            for sg_addr in addresses_by_type.get("aws_security_group", []):
                pair = (db_addr, sg_addr)
                if pair not in existing:
                    edges.append(DependencyEdge(source=db_addr, target=sg_addr))
                    existing.add(pair)
            for subnet_addr in addresses_by_type.get("aws_db_subnet_group", []):
                pair = (db_addr, subnet_addr)
                if pair not in existing:
                    edges.append(DependencyEdge(source=db_addr, target=subnet_addr))
                    existing.add(pair)

    # Pattern: Security groups depend on VPC
    for sg_addr in addresses_by_type.get("aws_security_group", []):
        for vpc_addr in addresses_by_type.get("aws_vpc", []):
            pair = (sg_addr, vpc_addr)
            if pair not in existing:
                edges.append(DependencyEdge(source=sg_addr, target=vpc_addr))
                existing.add(pair)

    # Pattern: Subnets depend on VPC
    for sn_addr in addresses_by_type.get("aws_subnet", []):
        for vpc_addr in addresses_by_type.get("aws_vpc", []):
            pair = (sn_addr, vpc_addr)
            if pair not in existing:
                edges.append(DependencyEdge(source=sn_addr, target=vpc_addr))
                existing.add(pair)

    # Pattern: DB subnet group depends on subnets
    for dbsg_addr in addresses_by_type.get("aws_db_subnet_group", []):
        for sn_addr in list(addresses_by_type.get("aws_subnet", [])):
            pair = (dbsg_addr, sn_addr)
            if pair not in existing:
                edges.append(DependencyEdge(source=dbsg_addr, target=sn_addr))
                existing.add(pair)

    # Pattern: ECR repo depends on nothing but other resources may depend on it (compute)
    for ecr_addr in addresses_by_type.get("aws_ecr_repository", []):
        for ec2_addr in list(
            addresses_by_type.get("aws_instance", [])
            + addresses_by_type.get("aws_ecs_service", [])
        ):
            pair = (ec2_addr, ecr_addr)
            if pair not in existing:
                edges.append(DependencyEdge(source=ec2_addr, target=ecr_addr))
                existing.add(pair)


# ── Blast-Radius Calculator ───────────────────────────────────────────────────

def _count_downstream(address: str, edges: List[DependencyEdge]) -> int:
    """
    Count distinct resources that depend on `address` (downstream fan-out).
    Uses BFS over the dependency graph.
    """
    targets_of: Dict[str, List[str]] = {}
    for e in edges:
        targets_of.setdefault(e.target, []).append(e.source)

    visited = set()
    queue = [address]
    while queue:
        current = queue.pop(0)
        for downstream in targets_of.get(current, []):
            if downstream not in visited:
                visited.add(downstream)
                queue.append(downstream)
    return len(visited)


def calculate_blast_radius(
    resource_changes: List[ResourceChange],
    dependency_edges: List[DependencyEdge],
    plan_json: Dict[str, Any],
    plan_id: Optional[str] = None,
) -> BlastRadiusResult:
    """
    Deterministic blast-radius calculation.

    Score formula (capped at 100):
        base = sum of action_weight × (1 + category_penalty_if_destructive)
        downstream_bonus = sum(downstream_count × 3 for each destructive resource)
        raw = base + downstream_bonus
        score = min(100, raw)

    Thresholds:
        CRITICAL  >= 80
        HIGH      >= 50
        MEDIUM    >= 25
        LOW        < 25
    """
    if plan_id is None:
        plan_id = hashlib.sha256(
            json.dumps(plan_json, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]

    plan_hash = hashlib.sha256(
        json.dumps(plan_json, sort_keys=True, default=str).encode()
    ).hexdigest()

    adds = modifies = destroys = replaces = no_ops = 0
    warnings: List[str] = []
    affected_categories: set = set()
    base_score = 0

    for rc in resource_changes:
        action = rc.action
        if action == ChangeAction.ADD:
            adds += 1
        elif action == ChangeAction.MODIFY:
            modifies += 1
        elif action == ChangeAction.DESTROY:
            destroys += 1
        elif action == ChangeAction.REPLACE:
            replaces += 1
        elif action in (ChangeAction.NO_OP, ChangeAction.READ):
            no_ops += 1

        action_score = _ACTION_WEIGHTS.get(action, 0)
        category_penalty = 0
        if rc.is_destructive:
            category_penalty = _CATEGORY_PENALTIES.get(rc.category, 0)

        base_score += action_score + category_penalty
        if action not in (ChangeAction.NO_OP, ChangeAction.READ):
            affected_categories.add(rc.category.value)

        # Warnings for high-risk patterns
        if action == ChangeAction.DESTROY:
            warnings.append(
                f"DESTRUCTIVE: '{rc.address}' ({rc.resource_type}) will be DESTROYED. "
                "Data loss may be permanent."
            )
        elif action == ChangeAction.REPLACE:
            warnings.append(
                f"REPLACEMENT: '{rc.address}' ({rc.resource_type}) will be replaced "
                "(destroy then re-create). Downtime likely."
            )
        if rc.category == ResourceCategory.DATABASE and rc.is_destructive:
            warnings.append(
                f"DATA RISK: Database resource '{rc.address}' is being modified destructively. "
                "Ensure a backup exists before applying."
            )
        if rc.category == ResourceCategory.NETWORK and action == ChangeAction.MODIFY:
            warnings.append(
                f"NETWORK IMPACT: Network resource '{rc.address}' modification "
                "may cause connectivity disruption."
            )
        if rc.category == ResourceCategory.SECURITY and rc.is_destructive:
            warnings.append(
                f"SECURITY ALERT: Security resource '{rc.address}' is being removed. "
                "Verify that dependent resources remain protected."
            )

    # Downstream fan-out bonus for destructive changes
    downstream_bonus = 0
    for rc in resource_changes:
        if rc.is_destructive:
            downstream_count = _count_downstream(rc.address, dependency_edges)
            downstream_bonus += downstream_count * 3

    raw_score = base_score + downstream_bonus
    score = min(100, raw_score)

    # Level assignment
    if score >= 80:
        level = BlastLevel.CRITICAL
    elif score >= 50:
        level = BlastLevel.HIGH
    elif score >= 25:
        level = BlastLevel.MEDIUM
    else:
        level = BlastLevel.LOW

    total_changes = adds + modifies + destroys + replaces + no_ops

    # Human-readable summary
    action_parts = []
    if adds:
        action_parts.append(f"{adds} add")
    if modifies:
        action_parts.append(f"{modifies} modify")
    if destroys:
        action_parts.append(f"{destroys} destroy")
    if replaces:
        action_parts.append(f"{replaces} replace")
    if no_ops:
        action_parts.append(f"{no_ops} no-op")

    action_summary = ", ".join(action_parts) if action_parts else "no changes"
    summary = (
        f"Plan affects {total_changes} resources ({action_summary}). "
        f"Blast radius: {level.value.upper()} (score {score}/100). "
        f"Affected layers: {', '.join(sorted(affected_categories)) or 'none'}."
    )

    return BlastRadiusResult(
        plan_id=plan_id,
        score=score,
        level=level,
        total_changes=total_changes,
        adds=adds,
        modifies=modifies,
        destroys=destroys,
        replaces=replaces,
        no_ops=no_ops,
        resource_changes=resource_changes,
        affected_categories=sorted(affected_categories),
        dependency_edges=dependency_edges,
        warnings=warnings,
        summary=summary,
        plan_hash=plan_hash,
    )


# ── Terraform CLI Runner ──────────────────────────────────────────────────────

# Explicit allow-list of safe Terraform subcommands (never includes 'apply')
_SAFE_TERRAFORM_COMMANDS = {"fmt", "validate", "plan", "show", "version", "init"}


def _run_terraform_command(
    args: List[str],
    cwd: str,
    timeout: int = 120,
) -> Tuple[int, str, str]:
    """
    Execute a terraform CLI subcommand inside `cwd` with an allow-list guard.
    Returns (return_code, stdout, stderr).
    Raises ValueError if the subcommand is not in the allow-list.
    """
    if not args:
        raise ValueError("No Terraform subcommand supplied")

    subcommand = args[0].lstrip("-")
    if subcommand not in _SAFE_TERRAFORM_COMMANDS:
        raise ValueError(
            f"Terraform subcommand '{subcommand}' is not permitted. "
            f"Allowed: {sorted(_SAFE_TERRAFORM_COMMANDS)}"
        )

    full_cmd = ["terraform"] + args
    try:
        proc = subprocess.run(
            full_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return -1, "", "terraform binary not found in PATH"
    except subprocess.TimeoutExpired:
        return -1, "", f"terraform command timed out after {timeout}s"
    except Exception as exc:
        return -1, "", str(exc)


def terraform_is_available() -> bool:
    """Check if the `terraform` binary is accessible on PATH."""
    rc, _, _ = _run_terraform_command(["version"], cwd=os.getcwd(), timeout=10)
    return rc == 0


# ── Mock Plan Generator ───────────────────────────────────────────────────────

def build_mock_plan_json(terraform_hcl: str, service_name: str = "api-service") -> Dict[str, Any]:
    """
    Produce a synthetic Terraform plan JSON object from a Terraform HCL string.
    Used when the terraform binary is unavailable or in test environments.

    The mock plan is derived deterministically from the HCL content:
    - Parses resource blocks using regex.
    - Assigns ADD action for each discovered resource (simulates first-time plan).
    - Builds a minimal Terraform plan JSON schema.
    """
    resource_pattern = re.compile(
        r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', re.MULTILINE
    )
    matches = resource_pattern.findall(terraform_hcl)

    resource_changes = []
    for res_type, res_name in matches:
        address = f"{res_type}.{res_name}"
        # Derive reasonable after-state values from common resource types
        after_state: Dict[str, Any] = {"id": f"mock-{res_name}-id"}
        if "vpc" in res_type:
            after_state.update({"cidr_block": "10.0.0.0/16", "enable_dns_hostnames": True})
        elif "subnet" in res_type:
            after_state.update({"cidr_block": "10.0.1.0/24", "vpc_id": "mock-vpc-id"})
        elif "security_group" in res_type:
            after_state.update({"name": f"{service_name}-sg", "vpc_id": "mock-vpc-id"})
        elif "db_instance" in res_type:
            after_state.update({
                "engine": "postgres",
                "engine_version": "16.3",
                "instance_class": "db.t3.micro",
                "db_name": service_name.replace("-", "_"),
                "username": "pgadmin",
                "allocated_storage": 20,
            })
        elif "db_subnet_group" in res_type:
            after_state.update({"name": f"{service_name}-db-subnet"})
        elif "ecr_repository" in res_type:
            after_state.update({
                "name": service_name,
                "image_tag_mutability": "MUTABLE",
            })

        resource_changes.append({
            "address": address,
            "module_address": None,
            "type": res_type,
            "name": res_name,
            "provider_name": f"registry.terraform.io/hashicorp/{res_type.split('_')[0]}",
            "change": {
                "actions": ["create"],
                "before": None,
                "after": after_state,
                "after_unknown": {},
                "before_sensitive": {},
                "after_sensitive": {},
                "action_reason": None,
            },
        })

    return {
        "format_version": "1.1",
        "terraform_version": "1.5.0-mock",
        "variables": {},
        "planned_values": {
            "root_module": {
                "resources": [
                    {
                        "address": rc["address"],
                        "type": rc["type"],
                        "name": rc["name"],
                        "values": rc["change"]["after"],
                    }
                    for rc in resource_changes
                ]
            }
        },
        "resource_changes": resource_changes,
        "configuration": {
            "root_module": {
                "resources": []
            }
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "errored": False,
        "_mock": True,
    }


# ── High-Level Orchestrator ───────────────────────────────────────────────────

def run_terraform_plan_analysis(
    terraform_hcl: str,
    service_name: str = "api-service",
    working_dir: Optional[str] = None,
    use_cli: bool = False,
) -> TerraformExecutionResult:
    """
    Main entry point for Terraform plan analysis.

    Strategy:
    1. If `use_cli=True` and terraform binary is available:
       a. Write HCL to a temp directory.
       b. Run `terraform fmt` → `terraform validate` → `terraform plan -out`.
       c. Run `terraform show -json` to get plan JSON.
       d. Parse and analyse the plan JSON.
    2. Otherwise (default safe path):
       a. Build a deterministic mock plan JSON from the HCL.
       b. Parse and analyse the mock plan.

    NEVER runs `terraform apply`.
    """
    if use_cli and terraform_is_available():
        return _run_with_cli(terraform_hcl, service_name, working_dir)
    else:
        return _run_with_mock(terraform_hcl, service_name)


def _run_with_mock(terraform_hcl: str, service_name: str) -> TerraformExecutionResult:
    """Execute plan analysis using the deterministic mock plan generator."""
    try:
        plan_json = build_mock_plan_json(terraform_hcl, service_name)
        resource_changes, dependency_edges = parse_plan_json(plan_json)
        blast = calculate_blast_radius(resource_changes, dependency_edges, plan_json)

        return TerraformExecutionResult(
            success=True,
            command="mock-plan (terraform binary not available)",
            stdout=json.dumps(plan_json, indent=2),
            stderr="",
            return_code=0,
            plan_json=plan_json,
            blast_radius=blast,
        )
    except Exception as exc:
        return TerraformExecutionResult(
            success=False,
            command="mock-plan",
            stdout="",
            stderr="",
            return_code=1,
            error=str(exc),
        )


def _run_with_cli(
    terraform_hcl: str,
    service_name: str,
    working_dir: Optional[str],
) -> TerraformExecutionResult:
    """Execute plan analysis using the real terraform CLI (allow-listed commands only)."""
    with tempfile.TemporaryDirectory(prefix="tf_plan_") as tmp_dir:
        tf_file = Path(tmp_dir) / "main.tf"
        tf_file.write_text(terraform_hcl, encoding="utf-8")

        plan_bin = Path(tmp_dir) / "plan.bin"
        plan_json_path = Path(tmp_dir) / "plan.json"

        # Step 1: Format (non-fatal)
        _run_terraform_command(["fmt", "-check", str(tf_file)], cwd=tmp_dir, timeout=30)

        # Step 2: Init (required before plan)
        rc_init, out_init, err_init = _run_terraform_command(
            ["init", "-backend=false", "-no-color"], cwd=tmp_dir, timeout=120
        )
        if rc_init != 0:
            return TerraformExecutionResult(
                success=False,
                command="terraform init",
                stdout=out_init,
                stderr=err_init,
                return_code=rc_init,
                error="terraform init failed — check provider configuration",
            )

        # Step 3: Validate
        rc_val, out_val, err_val = _run_terraform_command(
            ["validate", "-no-color"], cwd=tmp_dir, timeout=60
        )
        if rc_val != 0:
            return TerraformExecutionResult(
                success=False,
                command="terraform validate",
                stdout=out_val,
                stderr=err_val,
                return_code=rc_val,
                error="terraform validate failed",
            )

        # Step 4: Plan (exit code 2 means changes present, which is expected)
        rc_plan, out_plan, err_plan = _run_terraform_command(
            ["plan", "-out", str(plan_bin), "-no-color", "-input=false"],
            cwd=tmp_dir,
            timeout=120,
        )
        if rc_plan not in (0, 2):
            return TerraformExecutionResult(
                success=False,
                command="terraform plan",
                stdout=out_plan,
                stderr=err_plan,
                return_code=rc_plan,
                error="terraform plan failed",
            )

        # Step 5: Show plan as JSON
        rc_show, out_show, err_show = _run_terraform_command(
            ["show", "-json", str(plan_bin)],
            cwd=tmp_dir,
            timeout=60,
        )
        if rc_show != 0:
            return TerraformExecutionResult(
                success=False,
                command="terraform show",
                stdout=out_show,
                stderr=err_show,
                return_code=rc_show,
                error="terraform show -json failed",
            )

        try:
            plan_json = json.loads(out_show)
        except json.JSONDecodeError as exc:
            return TerraformExecutionResult(
                success=False,
                command="terraform show (json parse)",
                stdout=out_show,
                stderr="",
                return_code=0,
                error=f"Failed to parse plan JSON: {exc}",
            )

        resource_changes, dependency_edges = parse_plan_json(plan_json)
        blast = calculate_blast_radius(resource_changes, dependency_edges, plan_json)

        return TerraformExecutionResult(
            success=True,
            command="terraform plan + show -json",
            stdout=out_plan,
            stderr=err_plan,
            return_code=rc_plan,
            plan_json=plan_json,
            blast_radius=blast,
        )


# ── Serialization Helpers ─────────────────────────────────────────────────────

def blast_radius_to_dict(result: BlastRadiusResult) -> Dict[str, Any]:
    """Convert a BlastRadiusResult to a JSON-serializable dict for API responses."""
    return {
        "plan_id": result.plan_id,
        "score": result.score,
        "level": result.level.value,
        "total_changes": result.total_changes,
        "adds": result.adds,
        "modifies": result.modifies,
        "destroys": result.destroys,
        "replaces": result.replaces,
        "no_ops": result.no_ops,
        "affected_categories": result.affected_categories,
        "warnings": result.warnings,
        "summary": result.summary,
        "plan_hash": result.plan_hash,
        "created_at": result.created_at,
        "resource_changes": [
            {
                "address": rc.address,
                "resource_type": rc.resource_type,
                "resource_name": rc.resource_name,
                "provider": rc.provider,
                "action": rc.action.value,
                "category": rc.category.value,
                "is_destructive": rc.is_destructive,
                "affected_attributes": rc.affected_attributes,
                "replacement_forced_by": rc.replacement_forced_by,
            }
            for rc in result.resource_changes
        ],
        "dependency_edges": [
            {"source": e.source, "target": e.target}
            for e in result.dependency_edges
        ],
    }


def execution_result_to_dict(result: TerraformExecutionResult) -> Dict[str, Any]:
    """Convert a TerraformExecutionResult to a JSON-serializable dict for API responses."""
    out: Dict[str, Any] = {
        "success": result.success,
        "command": result.command,
        "return_code": result.return_code,
        "stdout_preview": result.stdout[:2000] if result.stdout else "",
        "stderr_preview": result.stderr[:1000] if result.stderr else "",
        "error": result.error,
        "blast_radius": blast_radius_to_dict(result.blast_radius) if result.blast_radius else None,
        "has_plan_json": result.plan_json is not None,
    }
    return out
