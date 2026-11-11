"""
Infrastructure Governance & Approval Module
Implements OPA-equivalent policy rules in pure Python (deterministic, no OPA binary required).
Policies are structured identically to what OPA/Rego would express.

SAFETY CONTRACT:
- Provisioning is BLOCKED when any MANDATORY policy fails.
- The approved plan hash must match the plan being applied (stale-plan detection).
- LLM never overrides policy decisions.
- approve/reject are explicit human actions only.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import ValidationError
from infra_platform.infrastructure.requirement_parser import InfrastructureSpec


# ── Enumerations ──────────────────────────────────────────────────────────────

class PolicyResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class PolicySeverity(str, Enum):
    MANDATORY = "mandatory"   # Failure blocks provisioning
    WARNING   = "warning"     # Failure warns but does not block


class ApprovalStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class PolicyViolation:
    policy_id: str
    result: PolicyResult
    severity: PolicySeverity
    message: str
    details: Optional[str] = None


@dataclass
class GovernanceReport:
    passed: List[PolicyViolation] = field(default_factory=list)
    failed: List[PolicyViolation] = field(default_factory=list)
    warnings: List[PolicyViolation] = field(default_factory=list)
    provisioning_allowed: bool = True
    summary: str = ""
    plan_hash: str = ""
    evaluated_at: float = field(default_factory=time.time)

    @property
    def all_violations(self) -> List[PolicyViolation]:
        return self.failed + self.warnings


@dataclass
class ApprovalRecord:
    approval_id: str
    plan_hash: str
    spec_hash: str
    service_name: str
    approved_by: str
    status: ApprovalStatus
    governance_report: GovernanceReport
    created_at: float = field(default_factory=time.time)
    decided_at: Optional[float] = None
    rejection_reason: Optional[str] = None


# ── In-memory approval store (stateless across restarts — Step 8 adds DB) ────
_APPROVAL_STORE: Dict[str, ApprovalRecord] = {}


# ── Policy Engine ─────────────────────────────────────────────────────────────

def _p(pid: str, result: PolicyResult, severity: PolicySeverity, msg: str, details: str = None) -> PolicyViolation:
    return PolicyViolation(policy_id=pid, result=result, severity=severity, message=msg, details=details)


def evaluate_policies(
    spec: Dict[str, Any],
    blast_radius: Optional[Dict[str, Any]] = None,
    plan_json: Optional[Dict[str, Any]] = None,
) -> GovernanceReport:
    """
    Evaluate all governance policies against an InfrastructureSpec dict
    and optional blast-radius / plan data.

    Policies mirror what an OPA/Rego bundle would express:
    - P001  Replica floor (MANDATORY)
    - P002  Replica ceiling (MANDATORY)
    - P003  Production replica minimum (MANDATORY)
    - P004  Worker public LoadBalancer (MANDATORY)
    - P005  Destructive change gate (MANDATORY)
    - P006  Production deletion protection (MANDATORY)
    - P007  High blast-radius warning (WARNING)
    - P008  Critical blast-radius block (MANDATORY)
    - P009  Database exposure warning (WARNING)
    - P010  Monitoring required in production (WARNING)
    """
    report = GovernanceReport()
    passed, failed, warnings = [], [], []

    env   = spec.get("environment", "")
    stype = spec.get("service_type", "")
    reps  = spec.get("replica_count", 1)
    db    = spec.get("database", "none")
    net   = spec.get("network_exposure", "cluster-ip")
    mon   = spec.get("monitoring", "none")
    sname = spec.get("service_name", "unknown")

    br_level  = (blast_radius or {}).get("level", "low")
    br_score  = (blast_radius or {}).get("score", 0)
    destroys  = (blast_radius or {}).get("destroys", 0)
    replaces  = (blast_radius or {}).get("replaces", 0)

    # P001 — Replica floor
    if reps < 1:
        failed.append(_p("P001", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            "Replica count must be at least 1.",
            f"Requested: {reps}"))
    else:
        passed.append(_p("P001", PolicyResult.PASS, PolicySeverity.MANDATORY,
            f"Replica count {reps} satisfies minimum threshold."))

    # P002 — Replica ceiling (max 20)
    if reps > 20:
        failed.append(_p("P002", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            f"Replica count {reps} exceeds maximum allowed limit of 20."))
    else:
        passed.append(_p("P002", PolicyResult.PASS, PolicySeverity.MANDATORY,
            f"Replica count {reps} within allowed range."))

    # P003 — Production replica minimum (must be >= 2)
    if env == "production" and reps < 2:
        failed.append(_p("P003", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            "Production services require at least 2 replicas for high availability.",
            f"Current: {reps}"))
    else:
        passed.append(_p("P003", PolicyResult.PASS, PolicySeverity.MANDATORY,
            "Production HA replica requirement satisfied."))

    # P004 — Worker with public LoadBalancer
    if stype == "worker" and net == "load-balancer":
        failed.append(_p("P004", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            "Background workers must not be publicly exposed via LoadBalancer.",
            "Use cluster-ip or node-port for worker services."))
    else:
        passed.append(_p("P004", PolicyResult.PASS, PolicySeverity.MANDATORY,
            "Network exposure policy satisfied for service type."))

    # P005 — Destructive change gate
    if destroys > 0:
        failed.append(_p("P005", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            f"Plan contains {destroys} DESTROY action(s). Destructive changes require explicit approval.",
            "Review the blast-radius report and confirm data backup before approving."))
    else:
        passed.append(_p("P005", PolicyResult.PASS, PolicySeverity.MANDATORY,
            "No destructive resource changes detected."))

    # P006 — Production deletion protection for databases
    if env == "production" and db != "none" and destroys > 0:
        failed.append(_p("P006", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            "Destroying database resources in production is blocked without confirmed backup.",
            "Verify deletion_protection = true in Terraform config."))
    else:
        passed.append(_p("P006", PolicyResult.PASS, PolicySeverity.MANDATORY,
            "Database deletion protection policy satisfied."))

    # P007 — High blast-radius warning
    if br_level in ("high",):
        warnings.append(_p("P007", PolicyResult.WARN, PolicySeverity.WARNING,
            f"Blast radius is HIGH (score {br_score}/100). Carefully review affected resources.",
            "Consider scheduling during a maintenance window."))
    else:
        passed.append(_p("P007", PolicyResult.PASS, PolicySeverity.WARNING,
            f"Blast radius level '{br_level}' is acceptable."))

    # P008 — Critical blast-radius block
    if br_level == "critical":
        failed.append(_p("P008", PolicyResult.FAIL, PolicySeverity.MANDATORY,
            f"Blast radius is CRITICAL (score {br_score}/100). Provisioning blocked.",
            "Break the change into smaller increments or obtain elevated approval."))
    else:
        passed.append(_p("P008", PolicyResult.PASS, PolicySeverity.MANDATORY,
            f"Blast radius score {br_score} does not trigger critical block."))

    # P009 — Database with public LoadBalancer warning
    if db != "none" and net == "load-balancer" and stype == "worker":
        warnings.append(_p("P009", PolicyResult.WARN, PolicySeverity.WARNING,
            "Service with database access is publicly exposed. Ensure firewall rules are restrictive."))
    else:
        passed.append(_p("P009", PolicyResult.PASS, PolicySeverity.WARNING,
            "Database network exposure policy satisfied."))

    # P010 — Monitoring required in production
    if env == "production" and mon == "none":
        warnings.append(_p("P010", PolicyResult.WARN, PolicySeverity.WARNING,
            "Production services should have monitoring enabled.",
            "Enable prometheus-grafana or basic monitoring."))
    else:
        passed.append(_p("P010", PolicyResult.PASS, PolicySeverity.WARNING,
            "Monitoring policy satisfied."))

    # Build plan hash for stale-plan detection
    plan_hash = ""
    if plan_json:
        plan_hash = hashlib.sha256(
            json.dumps(plan_json, sort_keys=True, default=str).encode()
        ).hexdigest()

    report.passed = passed
    report.failed = failed
    report.warnings = warnings
    report.plan_hash = plan_hash
    report.provisioning_allowed = len(failed) == 0

    fail_count = len(failed)
    warn_count = len(warnings)
    pass_count = len(passed)
    status = "BLOCKED" if fail_count else ("WARNINGS" if warn_count else "CLEAR")
    report.summary = (
        f"Policy evaluation: {pass_count} passed, {fail_count} failed, {warn_count} warnings. "
        f"Provisioning: {status}."
    )
    return report


def canonicalize_infrastructure_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return a validated specification with defaults, or preserve invalid input."""
    try:
        normalized = InfrastructureSpec(**spec)
        return (
            normalized.model_dump(mode="json")
            if hasattr(normalized, "model_dump")
            else normalized.dict()
        )
    except ValidationError:
        return spec


def infrastructure_spec_hash(spec: Dict[str, Any]) -> str:
    """Hash the validated, canonical form of a provisioning specification."""
    canonical_spec = canonicalize_infrastructure_spec(spec)
    return hashlib.sha256(
        json.dumps(canonical_spec, sort_keys=True, default=str).encode()
    ).hexdigest()


# ── Approval Workflow ─────────────────────────────────────────────────────────

def submit_for_approval(
    spec: Dict[str, Any],
    governance_report: GovernanceReport,
    requester: str = "system",
    plan_json: Optional[Dict[str, Any]] = None,
) -> ApprovalRecord:
    """
    Create an ApprovalRecord for the given spec + governance report.
    Returns the pending record. Only records where provisioning_allowed=True
    can proceed to approval; others are immediately REJECTED.
    """
    import uuid
    approval_id = str(uuid.uuid4())[:12]
    canonical_spec = canonicalize_infrastructure_spec(spec)
    service_name = canonical_spec.get("service_name", "unknown")
    spec_hash = hashlib.sha256(
        json.dumps(canonical_spec, sort_keys=True, default=str).encode()
    ).hexdigest()

    plan_hash = governance_report.plan_hash
    if not plan_hash and plan_json:
        plan_hash = hashlib.sha256(
            json.dumps(plan_json, sort_keys=True, default=str).encode()
        ).hexdigest()

    if not governance_report.provisioning_allowed:
        status = ApprovalStatus.REJECTED
        decided_at = time.time()
        reason = "Auto-rejected: mandatory policy failures detected."
    else:
        status = ApprovalStatus.PENDING
        decided_at = None
        reason = None

    record = ApprovalRecord(
        approval_id=approval_id,
        plan_hash=plan_hash,
        spec_hash=spec_hash,
        service_name=service_name,
        approved_by=requester,
        status=status,
        governance_report=governance_report,
        decided_at=decided_at,
        rejection_reason=reason,
    )
    _APPROVAL_STORE[approval_id] = record
    return record


def approve_plan(approval_id: str, approver: str, current_plan_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Approve a pending plan. Re-validates plan hash integrity before granting approval.
    Returns dict with success, approval_id, stale_plan, message.
    """
    record = _APPROVAL_STORE.get(approval_id)
    if not record:
        return {"success": False, "error": f"Approval ID '{approval_id}' not found."}

    if record.status == ApprovalStatus.REJECTED:
        return {"success": False, "error": "Plan was already rejected due to policy failures."}
    if record.status == ApprovalStatus.APPROVED:
        return {"success": False, "error": "Plan is already approved."}

    # Stale-plan detection: if a new plan_json is provided, verify hash matches
    stale = False
    if current_plan_json and record.plan_hash:
        current_hash = hashlib.sha256(
            json.dumps(current_plan_json, sort_keys=True, default=str).encode()
        ).hexdigest()
        if current_hash != record.plan_hash:
            stale = True
            return {
                "success": False,
                "stale_plan": True,
                "error": "Plan has changed since governance evaluation. Re-run policy check before approving.",
                "original_hash": record.plan_hash,
                "current_hash": current_hash,
            }
    record.status = ApprovalStatus.APPROVED
    record.approved_by = approver
    record.decided_at = time.time()
    return {
        "success": True,
        "approval_id": approval_id,
        "stale_plan": stale,
        "message": f"Plan approved by '{approver}'. Safe to proceed with controlled provisioning.",
        "plan_hash": record.plan_hash,
    }


def reject_plan(approval_id: str, reason: str = "Rejected by operator") -> Dict[str, Any]:
    """Reject a pending plan. Idempotent for already-rejected plans."""
    record = _APPROVAL_STORE.get(approval_id)
    if not record:
        return {"success": False, "error": f"Approval ID '{approval_id}' not found."}
    if record.status == ApprovalStatus.APPROVED:
        return {"success": False, "error": "Cannot reject an already-approved plan."}

    record.status = ApprovalStatus.REJECTED
    record.decided_at = time.time()
    record.rejection_reason = reason
    return {
        "success": True,
        "approval_id": approval_id,
        "message": f"Plan rejected. Reason: {reason}",
    }


def get_approval(approval_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an approval record as a serializable dict."""
    record = _APPROVAL_STORE.get(approval_id)
    if not record:
        return None
    return _approval_to_dict(record)


def _approval_to_dict(record: ApprovalRecord) -> Dict[str, Any]:
    rpt = record.governance_report
    return {
        "approval_id": record.approval_id,
        "plan_hash": record.plan_hash,
        "spec_hash": record.spec_hash,
        "service_name": record.service_name,
        "approved_by": record.approved_by,
        "status": record.status.value,
        "created_at": record.created_at,
        "decided_at": record.decided_at,
        "rejection_reason": record.rejection_reason,
        "governance": {
            "provisioning_allowed": rpt.provisioning_allowed,
            "summary": rpt.summary,
            "passed_count": len(rpt.passed),
            "failed_count": len(rpt.failed),
            "warnings_count": len(rpt.warnings),
            "failed_policies": [
                {"id": v.policy_id, "severity": v.severity.value, "message": v.message, "details": v.details}
                for v in rpt.failed
            ],
            "warning_policies": [
                {"id": v.policy_id, "severity": v.severity.value, "message": v.message, "details": v.details}
                for v in rpt.warnings
            ],
            "passed_policies": [
                {"id": v.policy_id, "message": v.message}
                for v in rpt.passed
            ],
        },
    }


def governance_report_to_dict(report: GovernanceReport) -> Dict[str, Any]:
    return {
        "provisioning_allowed": report.provisioning_allowed,
        "summary": report.summary,
        "plan_hash": report.plan_hash,
        "evaluated_at": report.evaluated_at,
        "passed": [{"id": v.policy_id, "message": v.message} for v in report.passed],
        "failed": [
            {"id": v.policy_id, "severity": v.severity.value, "message": v.message, "details": v.details}
            for v in report.failed
        ],
        "warnings": [
            {"id": v.policy_id, "severity": v.severity.value, "message": v.message, "details": v.details}
            for v in report.warnings
        ],
    }
