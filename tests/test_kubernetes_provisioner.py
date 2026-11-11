import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import infra_platform.infrastructure.kubernetes_provisioner as provisioner
import main
from infra_platform.infrastructure.governance import infrastructure_spec_hash
from infra_platform.infrastructure.requirement_parser import (
    Environment,
    InfrastructureSpec,
    NetworkExposure,
    ServiceType,
)
from infra_platform.infrastructure.service_registry import DeploymentStatus, ServiceRegistry


def run_sync(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def workload_payload(ready_replicas=2):
    return {
        "kind": "List",
        "items": [
            {
                "kind": "Deployment",
                "metadata": {"name": "demo-api"},
                "spec": {"replicas": 2},
                "status": {
                    "readyReplicas": ready_replicas,
                    "availableReplicas": ready_replicas,
                },
            },
            {
                "kind": "Pod",
                "metadata": {"name": "demo-api-abc"},
                "status": {
                    "phase": "Running" if ready_replicas else "Pending",
                    "containerStatuses": [
                        {
                            "name": "demo-api",
                            "ready": bool(ready_replicas),
                            "restartCount": 1,
                            "state": (
                                {"running": {}}
                                if ready_replicas
                                else {
                                    "waiting": {
                                        "reason": "ImagePullBackOff",
                                        "message": "image not found",
                                    }
                                }
                            ),
                        }
                    ],
                },
            },
            {
                "kind": "Service",
                "metadata": {"name": "demo-api-service"},
                "spec": {
                    "type": "ClusterIP",
                    "clusterIP": "10.96.0.5",
                    "ports": [{"port": 80, "targetPort": 8000}],
                },
                "status": {"loadBalancer": {"ingress": []}},
            },
        ],
    }


def install_fake_tools(monkeypatch, *, server="https://127.0.0.1:6443", ready=2, rollout_fails=False):
    monkeypatch.setattr(provisioner.shutil, "which", lambda name: f"C:\\tools\\{name}.exe")
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if command[0].endswith("kind.exe"):
            return SimpleNamespace(stdout="local\n", stderr="")
        if "config" in command:
            return SimpleNamespace(stdout=server, stderr="")
        if "apply" in command:
            return SimpleNamespace(stdout="applied", stderr="")
        if "rollout" in command:
            if rollout_fails:
                raise subprocess.CalledProcessError(
                    1, command, output="", stderr="deployment exceeded its progress deadline"
                )
            return SimpleNamespace(stdout="deployment successfully rolled out", stderr="")
        if "get" in command:
            return SimpleNamespace(stdout=json.dumps(workload_payload(ready)), stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(provisioner.subprocess, "run", fake_run)
    return commands


def demo_spec(**overrides):
    values = {
        "service_name": "demo-api",
        "service_type": ServiceType.WEB_API,
        "environment": Environment.DEVELOPMENT,
        "replica_count": 2,
        "database": "none",
        "network_exposure": NetworkExposure.CLUSTER_IP,
        "monitoring": "basic",
    }
    values.update(overrides)
    return InfrastructureSpec(**values)


def test_local_kind_deployment_uses_generated_manifests_and_explicit_context(monkeypatch):
    commands = install_fake_tools(monkeypatch)

    result = provisioner.deploy_spec_to_kind(demo_spec(), "local")

    assert result["success"] is True
    assert result["deployment_status"] == "ready"
    assert result["namespace"] == "demo-api-development"
    assert result["deployments"][0]["ready_replicas"] == 2
    assert result["services"][0]["name"] == "demo-api-service"
    apply_command, apply_kwargs = next(
        (command, kwargs) for command, kwargs in commands if "apply" in command
    )
    assert "--context=kind-local" in apply_command
    assert apply_kwargs["input"].startswith("# === Kubernetes Manifests")
    assert all(kwargs.get("shell") is not True for _, kwargs in commands)


def test_remote_kubernetes_context_is_rejected_before_apply(monkeypatch):
    commands = install_fake_tools(monkeypatch, server="https://192.0.2.10:6443")

    with pytest.raises(provisioner.KubernetesProvisioningError) as error:
        provisioner.deploy_spec_to_kind(demo_spec(), "local")

    assert error.value.status_code == 403
    assert not any("apply" in command for command, _ in commands)


def test_unknown_kind_cluster_is_rejected(monkeypatch):
    install_fake_tools(monkeypatch)
    monkeypatch.setattr(
        provisioner,
        "_run_command",
        lambda executable, args, **kwargs: "",
    )

    with pytest.raises(provisioner.KubernetesProvisioningError) as error:
        provisioner.get_kind_workload_status(
            "missing", "demo-api", "development"
        )

    assert error.value.status_code == 404


def test_missing_kind_binary_is_reported(monkeypatch):
    monkeypatch.setattr(provisioner.shutil, "which", lambda _: None)

    with pytest.raises(provisioner.KubernetesProvisioningError) as error:
        provisioner.list_kind_clusters()

    assert error.value.status_code == 503
    assert "kind" in str(error.value)


def test_rollout_failure_returns_workload_status_without_claiming_success(monkeypatch):
    install_fake_tools(monkeypatch, ready=0, rollout_fails=True)

    result = provisioner.deploy_spec_to_kind(demo_spec(), "local")

    assert result["success"] is False
    assert result["deployment_status"] == "not-ready"
    assert "progress deadline" in result["error"]
    assert result["pods"][0]["phase"] == "Pending"
    assert result["pods"][0]["container_states"][0]["reason"] == "ImagePullBackOff"


def test_status_endpoint_summarizes_and_updates_registered_workloads(monkeypatch, tmp_path):
    install_fake_tools(monkeypatch)
    registry = ServiceRegistry(tmp_path / "registry.sqlite3")
    registry.create_service("demo-api", "team", "development", 2)
    monkeypatch.setattr(main, "service_registry", registry)

    result = run_sync(
        main.kubernetes_status(
            "local", "demo-api", Environment.DEVELOPMENT
        )
    )

    assert result["ready"] is True
    assert result["deployments"][0]["name"] == "demo-api"
    assert result["pods"][0]["restart_count"] == 1
    assert result["services"][0]["type"] == "ClusterIP"
    registered = registry.get_service("demo-api", "development")
    assert registered["deployment_status"] == DeploymentStatus.RUNNING.value
    assert "service/demo-api-service" in registered["resource_references"]


def test_deploy_endpoint_requires_approved_governance(monkeypatch):
    request = main.KindDeployRequest(
        spec=demo_spec(),
        cluster_name="local",
        approval_id="approval-1",
    )
    monkeypatch.setattr(main, "get_approval", lambda _: None)
    deploy_called = False

    def fail_if_deployed(*args):
        nonlocal deploy_called
        deploy_called = True

    monkeypatch.setattr(main, "deploy_spec_to_kind", fail_if_deployed)

    with pytest.raises(HTTPException) as error:
        run_sync(main.kubernetes_deploy(request))

    assert error.value.status_code == 403
    assert deploy_called is False


def test_deploy_endpoint_rechecks_mandatory_policies(monkeypatch):
    request = main.KindDeployRequest(
        spec=demo_spec(
            service_type=ServiceType.WORKER,
            network_exposure=NetworkExposure.LOAD_BALANCER,
        ),
        cluster_name="local",
        approval_id="approval-1",
    )
    monkeypatch.setattr(
        main,
        "get_approval",
        lambda _: {
            "status": "approved",
            "service_name": "demo-api",
            "spec_hash": infrastructure_spec_hash(
                request.spec.model_dump(mode="json")
            ),
            "governance": {"provisioning_allowed": True},
        },
    )
    deploy_called = False

    def fail_if_deployed(*args):
        nonlocal deploy_called
        deploy_called = True

    monkeypatch.setattr(main, "deploy_spec_to_kind", fail_if_deployed)

    with pytest.raises(HTTPException) as error:
        run_sync(main.kubernetes_deploy(request))

    assert error.value.status_code == 403
    assert "P004" in str(error.value.detail)
    assert deploy_called is False


def test_deploy_endpoint_registers_matching_approved_deployment(monkeypatch, tmp_path):
    request = main.KindDeployRequest(
        spec=demo_spec(),
        cluster_name="local",
        approval_id="approval-1",
        owner="platform-team",
    )
    registry = ServiceRegistry(tmp_path / "registry.sqlite3")
    monkeypatch.setattr(main, "service_registry", registry)
    monkeypatch.setattr(
        main,
        "get_approval",
        lambda _: {
            "status": "approved",
            "service_name": "demo-api",
            "spec_hash": infrastructure_spec_hash(
                request.spec.model_dump(mode="json")
            ),
            "governance": {"provisioning_allowed": True},
        },
    )
    expected = {
        "success": True,
        "deployment_status": "ready",
        "namespace": "demo-api-development",
        "deployments": [{"name": "demo-api"}],
        "services": [{"name": "demo-api-service"}],
    }
    calls = []

    def fake_deploy(spec, cluster_name):
        calls.append((spec, cluster_name))
        return expected

    monkeypatch.setattr(main, "deploy_spec_to_kind", fake_deploy)

    result = run_sync(main.kubernetes_deploy(request))

    assert result["success"] is True
    registered = registry.get_service("demo-api", "development")
    assert registered["owner"] == "platform-team"
    assert registered["replica_count"] == 2
    assert registered["deployment_status"] == DeploymentStatus.RUNNING.value
    assert registered["resource_references"] == [
        "namespace/demo-api-development",
        "deployment/demo-api",
        "service/demo-api-service",
    ]
    assert calls == [(request.spec, "local")]


def test_deploy_endpoint_rejects_modified_approved_spec(monkeypatch):
    request = main.KindDeployRequest(
        spec=demo_spec(replica_count=3),
        cluster_name="local",
        approval_id="approval-1",
    )
    monkeypatch.setattr(
        main,
        "get_approval",
        lambda _: {
            "status": "approved",
            "service_name": "demo-api",
            "spec_hash": infrastructure_spec_hash(
                demo_spec(replica_count=2).model_dump(mode="json")
            ),
            "governance": {"provisioning_allowed": True},
        },
    )

    with pytest.raises(HTTPException) as error:
        run_sync(main.kubernetes_deploy(request))

    assert error.value.status_code == 403
    assert "specification does not match" in error.value.detail


def test_governance_approval_hashes_the_same_defaulted_spec_used_by_policies():
    raw_spec = {
        "service_name": "default-api",
        "service_type": "web-api",
        "environment": "production",
    }

    response = run_sync(
        main.governance_evaluate(
            main.GovernanceEvalRequest(spec=raw_spec, requester="operator")
        )
    )
    approval = main.get_approval(response["approval_id"])
    expected_spec = InfrastructureSpec(**raw_spec).model_dump(mode="json")

    assert response["provisioning_allowed"] is True
    assert approval["spec_hash"] == infrastructure_spec_hash(expected_spec)
