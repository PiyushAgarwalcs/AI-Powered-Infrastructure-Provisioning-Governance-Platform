"""
Governance tests for policy evaluation, approval/rejection lifecycle,
stale-plan detection, mandatory blocks, and API handlers.
"""
import pytest
from infra_platform.infrastructure.governance import (
    evaluate_policies, submit_for_approval, approve_plan, reject_plan,
    get_approval, governance_report_to_dict,
    PolicyResult, PolicySeverity, ApprovalStatus,
)
from main import governance_evaluate, governance_approve, governance_reject, GovernanceEvalRequest, ApproveRequest, RejectRequest


def run_sync(coro):
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


# ── Fixtures ──────────────────────────────────────────────────────────────────

PROD_SPEC = {
    "service_name": "payment-api",
    "service_type": "web-api",
    "environment": "production",
    "replica_count": 3,
    "database": "postgres",
    "network_exposure": "load-balancer",
    "monitoring": "prometheus-grafana",
}

DEV_SPEC = {
    "service_name": "dev-api",
    "service_type": "web-api",
    "environment": "development",
    "replica_count": 1,
    "database": "none",
    "network_exposure": "cluster-ip",
    "monitoring": "none",
}

CLEAN_BLAST = {"level": "low", "score": 10, "destroys": 0, "replaces": 0}
DESTRUCTIVE_BLAST = {"level": "high", "score": 60, "destroys": 2, "replaces": 0}
CRITICAL_BLAST = {"level": "critical", "score": 95, "destroys": 5, "replaces": 1}


# ── 1. Policy evaluation — passing cases ─────────────────────────────────────

class TestPolicyEvaluationPass:

    def test_clean_prod_spec_passes(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        assert report.provisioning_allowed is True
        assert len(report.failed) == 0

    def test_dev_spec_passes(self):
        report = evaluate_policies(DEV_SPEC, CLEAN_BLAST)
        assert report.provisioning_allowed is True

    def test_summary_contains_provisioning_status(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        assert "CLEAR" in report.summary or "WARNINGS" in report.summary or "BLOCKED" in report.summary

    def test_all_policies_evaluated(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        total = len(report.passed) + len(report.failed) + len(report.warnings)
        assert total == 10  # exactly 10 policies defined

    def test_passed_list_non_empty(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        assert len(report.passed) > 0


# ── 2. Policy evaluation — replica violations ─────────────────────────────────

class TestReplicaPolicies:

    def test_zero_replicas_blocked(self):
        spec = {**PROD_SPEC, "replica_count": 0}
        report = evaluate_policies(spec, CLEAN_BLAST)
        assert report.provisioning_allowed is False
        ids = [v.policy_id for v in report.failed]
        assert "P001" in ids

    def test_above_max_replicas_blocked(self):
        spec = {**PROD_SPEC, "replica_count": 25}
        report = evaluate_policies(spec, CLEAN_BLAST)
        assert report.provisioning_allowed is False
        ids = [v.policy_id for v in report.failed]
        assert "P002" in ids

    def test_production_requires_min_2_replicas(self):
        spec = {**PROD_SPEC, "replica_count": 1}
        report = evaluate_policies(spec, CLEAN_BLAST)
        assert report.provisioning_allowed is False
        ids = [v.policy_id for v in report.failed]
        assert "P003" in ids

    def test_dev_single_replica_allowed(self):
        report = evaluate_policies(DEV_SPEC, CLEAN_BLAST)
        # P003 passes for non-production
        ids = [v.policy_id for v in report.failed]
        assert "P003" not in ids


# ── 3. Policy evaluation — network exposure ───────────────────────────────────

class TestNetworkExposurePolicies:

    def test_worker_with_loadbalancer_blocked(self):
        spec = {**PROD_SPEC, "service_type": "worker", "network_exposure": "load-balancer"}
        report = evaluate_policies(spec, CLEAN_BLAST)
        assert report.provisioning_allowed is False
        ids = [v.policy_id for v in report.failed]
        assert "P004" in ids

    def test_worker_with_clusterip_allowed(self):
        spec = {**PROD_SPEC, "service_type": "worker", "network_exposure": "cluster-ip", "database": "redis"}
        report = evaluate_policies(spec, CLEAN_BLAST)
        ids = [v.policy_id for v in report.failed]
        assert "P004" not in ids

    def test_webapi_with_loadbalancer_allowed(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        ids = [v.policy_id for v in report.failed]
        assert "P004" not in ids


# ── 4. Policy evaluation — destructive changes ────────────────────────────────

class TestDestructivePolicies:

    def test_destroys_trigger_p005(self):
        report = evaluate_policies(PROD_SPEC, DESTRUCTIVE_BLAST)
        assert report.provisioning_allowed is False
        ids = [v.policy_id for v in report.failed]
        assert "P005" in ids

    def test_production_db_destroy_triggers_p006(self):
        report = evaluate_policies(PROD_SPEC, DESTRUCTIVE_BLAST)
        ids = [v.policy_id for v in report.failed]
        assert "P006" in ids

    def test_dev_db_destroy_does_not_trigger_p006(self):
        spec = {**DEV_SPEC, "database": "postgres"}
        report = evaluate_policies(spec, DESTRUCTIVE_BLAST)
        ids = [v.policy_id for v in report.failed]
        # P005 fires, P006 should NOT fire (not production)
        assert "P006" not in ids

    def test_no_destroys_p005_passes(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        ids = [v.policy_id for v in report.failed]
        assert "P005" not in ids


# ── 5. Policy evaluation — blast-radius thresholds ───────────────────────────

class TestBlastRadiusPolicies:

    def test_high_blast_generates_p007_warning(self):
        report = evaluate_policies(DEV_SPEC, {"level": "high", "score": 55, "destroys": 0, "replaces": 0})
        ids = [v.policy_id for v in report.warnings]
        assert "P007" in ids

    def test_critical_blast_blocked_by_p008(self):
        report = evaluate_policies(DEV_SPEC, CRITICAL_BLAST)
        assert report.provisioning_allowed is False
        ids = [v.policy_id for v in report.failed]
        assert "P008" in ids

    def test_low_blast_no_p007_p008_failures(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        ids_failed = [v.policy_id for v in report.failed]
        ids_warn = [v.policy_id for v in report.warnings]
        assert "P008" not in ids_failed
        assert "P007" not in ids_warn


# ── 6. Policy evaluation — monitoring ────────────────────────────────────────

class TestMonitoringPolicy:

    def test_production_without_monitoring_warns(self):
        spec = {**PROD_SPEC, "monitoring": "none"}
        report = evaluate_policies(spec, CLEAN_BLAST)
        ids = [v.policy_id for v in report.warnings]
        assert "P010" in ids

    def test_production_with_monitoring_passes(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        ids = [v.policy_id for v in report.warnings]
        assert "P010" not in ids


# ── 7. Approval lifecycle ─────────────────────────────────────────────────────

class TestApprovalLifecycle:

    def test_clean_plan_submits_as_pending(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        record = submit_for_approval(PROD_SPEC, report)
        assert record.status == ApprovalStatus.PENDING

    def test_policy_failed_plan_auto_rejected(self):
        spec = {**PROD_SPEC, "replica_count": 0}
        report = evaluate_policies(spec, CLEAN_BLAST)
        record = submit_for_approval(spec, report)
        assert record.status == ApprovalStatus.REJECTED

    def test_approve_pending_plan(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        record = submit_for_approval(PROD_SPEC, report)
        result = approve_plan(record.approval_id, "admin")
        assert result["success"] is True
        assert result["approval_id"] == record.approval_id

    def test_reject_pending_plan(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        record = submit_for_approval(PROD_SPEC, report)
        result = reject_plan(record.approval_id, "Change rejected by security team")
        assert result["success"] is True

    def test_cannot_approve_rejected_plan(self):
        spec = {**PROD_SPEC, "replica_count": 0}
        report = evaluate_policies(spec, CLEAN_BLAST)
        record = submit_for_approval(spec, report)
        result = approve_plan(record.approval_id, "admin")
        assert result["success"] is False

    def test_cannot_reject_approved_plan(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        record = submit_for_approval(PROD_SPEC, report)
        approve_plan(record.approval_id, "admin")
        result = reject_plan(record.approval_id, "too late")
        assert result["success"] is False

    def test_unknown_approval_id_returns_error(self):
        result = approve_plan("nonexistent-id", "admin")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_get_approval_returns_dict(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        record = submit_for_approval(PROD_SPEC, report)
        data = get_approval(record.approval_id)
        assert data is not None
        assert data["approval_id"] == record.approval_id
        assert "governance" in data

    def test_get_unknown_approval_returns_none(self):
        assert get_approval("bad-id") is None


# ── 8. Stale-plan detection ───────────────────────────────────────────────────

class TestStalePlanDetection:

    def test_matching_plan_hash_approves(self):
        plan_json = {"resource_changes": [{"type": "aws_vpc", "name": "main"}]}
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST, plan_json=plan_json)
        record = submit_for_approval(PROD_SPEC, report, plan_json=plan_json)
        result = approve_plan(record.approval_id, "admin", current_plan_json=plan_json)
        assert result["success"] is True
        assert result.get("stale_plan") is not True

    def test_changed_plan_blocks_approval(self):
        original_plan = {"resource_changes": [{"type": "aws_vpc", "name": "main"}]}
        modified_plan = {"resource_changes": [{"type": "aws_vpc", "name": "main"}, {"type": "aws_db_instance", "name": "new"}]}
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST, plan_json=original_plan)
        record = submit_for_approval(PROD_SPEC, report, plan_json=original_plan)
        result = approve_plan(record.approval_id, "admin", current_plan_json=modified_plan)
        assert result["success"] is False
        assert result.get("stale_plan") is True


# ── 9. Serialization ──────────────────────────────────────────────────────────

class TestSerialization:

    def test_governance_report_to_dict_has_required_keys(self):
        report = evaluate_policies(PROD_SPEC, CLEAN_BLAST)
        d = governance_report_to_dict(report)
        for key in ("provisioning_allowed", "summary", "passed", "failed", "warnings", "plan_hash"):
            assert key in d

    def test_governance_report_json_serializable(self):
        import json
        report = evaluate_policies(PROD_SPEC, DESTRUCTIVE_BLAST)
        d = governance_report_to_dict(report)
        encoded = json.dumps(d)
        decoded = json.loads(encoded)
        assert decoded["provisioning_allowed"] is False


# ── 10. API endpoint handlers ─────────────────────────────────────────────────

class TestGovernanceApiEndpoints:

    def test_evaluate_endpoint_clean_spec(self):
        req = GovernanceEvalRequest(spec=PROD_SPEC, blast_radius=CLEAN_BLAST, requester="ops")
        resp = run_sync(governance_evaluate(req))
        assert resp["provisioning_allowed"] is True
        assert "approval_id" in resp
        assert resp["approval_status"] == "pending"

    def test_evaluate_endpoint_bad_spec_blocked(self):
        bad_spec = {**PROD_SPEC, "replica_count": 0}
        req = GovernanceEvalRequest(spec=bad_spec, blast_radius=CLEAN_BLAST)
        resp = run_sync(governance_evaluate(req))
        assert resp["provisioning_allowed"] is False
        assert resp["approval_status"] == "rejected"

    def test_evaluate_endpoint_destructive_blocked(self):
        req = GovernanceEvalRequest(spec=PROD_SPEC, blast_radius=DESTRUCTIVE_BLAST)
        resp = run_sync(governance_evaluate(req))
        assert resp["provisioning_allowed"] is False

    def test_approve_endpoint(self):
        req_eval = GovernanceEvalRequest(spec=PROD_SPEC, blast_radius=CLEAN_BLAST, requester="dev")
        resp_eval = run_sync(governance_evaluate(req_eval))
        approval_id = resp_eval["approval_id"]
        req_approve = ApproveRequest(approval_id=approval_id, approver="admin")
        resp_approve = run_sync(governance_approve(req_approve))
        assert resp_approve["success"] is True

    def test_reject_endpoint(self):
        req_eval = GovernanceEvalRequest(spec=PROD_SPEC, blast_radius=CLEAN_BLAST, requester="dev")
        resp_eval = run_sync(governance_evaluate(req_eval))
        approval_id = resp_eval["approval_id"]
        req_reject = RejectRequest(approval_id=approval_id, reason="Security review failed")
        resp_reject = run_sync(governance_reject(req_reject))
        assert resp_reject["success"] is True

    def test_critical_blast_blocked_at_endpoint(self):
        req = GovernanceEvalRequest(spec=PROD_SPEC, blast_radius=CRITICAL_BLAST)
        resp = run_sync(governance_evaluate(req))
        assert resp["provisioning_allowed"] is False
        # Check P008 in failed policies
        failed_ids = [p["id"] for p in resp["governance"]["failed"]]
        assert "P008" in failed_ids
