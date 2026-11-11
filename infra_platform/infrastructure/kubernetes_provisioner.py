"""Controlled provisioning and status inspection for local Kind clusters."""
import ipaddress
import json
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

from infra_platform.infrastructure.config_validator import validate_kubernetes_manifests
from infra_platform.infrastructure.generators import generate_kubernetes_for_spec
from infra_platform.infrastructure.requirement_parser import InfrastructureSpec


_CLUSTER_NAME = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,61}[a-z0-9])?")
_NAMESPACE_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ALLOWED_KINDS = {
    "Namespace",
    "ConfigMap",
    "Secret",
    "Deployment",
    "Service",
    "HorizontalPodAutoscaler",
}


class KubernetesProvisioningError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _required_binary(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise KubernetesProvisioningError(
            f"Required local tool '{name}' was not found on PATH.", 503
        )
    return executable


def _run_command(
    executable: str,
    args: List[str],
    *,
    input_text: Optional[str] = None,
    timeout: int = 30,
) -> str:
    try:
        result = subprocess.run(
            [executable, *args],
            input=input_text,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise KubernetesProvisioningError(
            f"Local Kubernetes command timed out after {timeout} seconds.", 504
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "command failed").strip()
        raise KubernetesProvisioningError(detail[:1000], 502) from exc
    except OSError as exc:
        raise KubernetesProvisioningError(
            f"Unable to run local Kubernetes tool: {exc}", 503
        ) from exc
    return result.stdout.strip()


def _validate_cluster_name(cluster_name: str) -> None:
    if not _CLUSTER_NAME.fullmatch(cluster_name or ""):
        raise KubernetesProvisioningError("Invalid Kind cluster name.", 400)


def list_kind_clusters() -> List[str]:
    kind = _required_binary("kind")
    output = _run_command(kind, ["get", "clusters"], timeout=15)
    clusters = []
    for line in output.splitlines():
        name = line.strip()
        if _CLUSTER_NAME.fullmatch(name):
            clusters.append(name)
    return clusters


def _local_context(cluster_name: str) -> str:
    _validate_cluster_name(cluster_name)
    if cluster_name not in list_kind_clusters():
        raise KubernetesProvisioningError(
            f"Kind cluster '{cluster_name}' does not exist.", 404
        )

    kubectl = _required_binary("kubectl")
    context = f"kind-{cluster_name}"
    server = _run_command(
        kubectl,
        [
            "config",
            "view",
            "--minify",
            f"--context={context}",
            "-o",
            "jsonpath={.clusters[0].cluster.server}",
        ],
        timeout=15,
    )
    parsed = urlparse(server)
    hostname = parsed.hostname or ""
    is_loopback = hostname == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False
    if parsed.scheme not in ("http", "https") or not is_loopback:
        raise KubernetesProvisioningError(
            f"Context '{context}' does not point to a local loopback Kubernetes API.",
            403,
        )
    return context


def _namespace_for_spec(spec: InfrastructureSpec) -> str:
    namespace = f"{spec.service_name}-{spec.environment.value}"
    if len(namespace) > 63 or not _NAMESPACE_NAME.fullmatch(namespace):
        raise KubernetesProvisioningError(
            "Service name and environment do not form a valid Kubernetes namespace.",
            400,
        )
    return namespace


def _validate_generated_manifests(manifest: str, namespace: str) -> None:
    validation = validate_kubernetes_manifests(
        manifest, require_deployment_and_service=True
    )
    if not validation["valid"]:
        raise KubernetesProvisioningError(
            "Generated Kubernetes manifests failed validation: "
            + "; ".join(validation["errors"]),
            400,
        )

    try:
        documents = [doc for doc in yaml.safe_load_all(manifest) if doc]
    except yaml.YAMLError as exc:
        raise KubernetesProvisioningError(
            f"Unable to parse generated Kubernetes manifests: {exc}", 400
        ) from exc

    for document in documents:
        kind = document.get("kind")
        metadata = document.get("metadata") or {}
        if kind not in _ALLOWED_KINDS:
            raise KubernetesProvisioningError(
                f"Generated manifest contains unsupported resource kind '{kind}'.",
                400,
            )
        if kind == "Namespace":
            if metadata.get("name") != namespace:
                raise KubernetesProvisioningError(
                    "Generated Namespace does not match the requested service.",
                    400,
                )
        elif metadata.get("namespace") != namespace:
            raise KubernetesProvisioningError(
                f"Generated {kind} is outside the expected namespace.", 400
            )


def _workload_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise KubernetesProvisioningError(
            "kubectl returned an invalid workload response.", 502
        )

    deployments = []
    pods = []
    services = []
    for item in items:
        if not isinstance(item, dict):
            raise KubernetesProvisioningError(
                "kubectl returned an invalid workload entry.", 502
            )
        kind = item.get("kind")
        metadata = item.get("metadata") or {}
        spec = item.get("spec") or {}
        status = item.get("status") or {}
        name = metadata.get("name")
        if not name:
            continue

        if kind == "Deployment":
            deployments.append({
                "name": name,
                "desired_replicas": spec.get("replicas") or 0,
                "ready_replicas": status.get("readyReplicas") or 0,
                "available_replicas": status.get("availableReplicas") or 0,
            })
        elif kind == "Pod":
            container_statuses = status.get("containerStatuses") or []
            pod_container_states = []
            for container in container_statuses:
                container_state = container.get("state") or {}
                state_name, state_details = next(
                    iter(container_state.items()), ("unknown", {})
                )
                pod_container_states.append({
                    "name": container.get("name"),
                    "state": state_name,
                    "reason": state_details.get("reason"),
                    "message": state_details.get("message"),
                })
            pods.append({
                "name": name,
                "phase": status.get("phase", "Unknown"),
                "ready": bool(container_statuses)
                and all(container.get("ready", False) for container in container_statuses),
                "restart_count": sum(
                    container.get("restartCount") or 0
                    for container in container_statuses
                ),
                "container_states": pod_container_states,
            })
        elif kind == "Service":
            services.append({
                "name": name,
                "type": spec.get("type", "ClusterIP"),
                "cluster_ip": spec.get("clusterIP"),
                "ports": spec.get("ports") or [],
                "load_balancer": (status.get("loadBalancer") or {}).get("ingress", []),
            })

    return {
        "deployments": deployments,
        "pods": pods,
        "services": services,
        "ready": bool(deployments) and all(
            deployment["ready_replicas"] >= deployment["desired_replicas"]
            for deployment in deployments
        ),
    }


def _get_workloads(context: str, namespace: str) -> Dict[str, Any]:
    kubectl = _required_binary("kubectl")
    output = _run_command(
        kubectl,
        [
            f"--context={context}",
            "get",
            "deployments,pods,services",
            f"--namespace={namespace}",
            "-o",
            "json",
            "--request-timeout=10s",
        ],
        timeout=15,
    )
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise KubernetesProvisioningError(
            "kubectl returned malformed JSON for workload status.", 502
        ) from exc
    if not isinstance(payload, dict):
        raise KubernetesProvisioningError(
            "kubectl returned an invalid workload response.", 502
        )
    return _workload_summary(payload)


def get_kind_workload_status(
    cluster_name: str,
    service_name: str,
    environment: str,
) -> Dict[str, Any]:
    try:
        spec = InfrastructureSpec(
            service_name=service_name,
            environment=environment,
        )
    except Exception as exc:
        raise KubernetesProvisioningError(
            f"Invalid service or environment: {exc}", 400
        ) from exc
    namespace = _namespace_for_spec(spec)
    context = _local_context(cluster_name)
    return {
        "cluster_name": cluster_name,
        "namespace": namespace,
        **_get_workloads(context, namespace),
    }


def deploy_spec_to_kind(
    spec: InfrastructureSpec,
    cluster_name: str,
) -> Dict[str, Any]:
    namespace = _namespace_for_spec(spec)
    manifest = generate_kubernetes_for_spec(spec)
    _validate_generated_manifests(manifest, namespace)
    context = _local_context(cluster_name)
    kubectl = _required_binary("kubectl")

    apply_output = _run_command(
        kubectl,
        [
            f"--context={context}",
            "apply",
            "--filename=-",
            "--request-timeout=15s",
        ],
        input_text=manifest,
        timeout=60,
    )

    rollout_error = None
    try:
        _run_command(
            kubectl,
            [
                f"--context={context}",
                "rollout",
                "status",
                f"deployment/{spec.service_name}",
                f"--namespace={namespace}",
                "--timeout=120s",
            ],
            timeout=130,
        )
    except KubernetesProvisioningError as exc:
        rollout_error = str(exc)

    workloads = _get_workloads(context, namespace)
    application_ready = any(
        deployment["name"] == spec.service_name
        and deployment["ready_replicas"] >= deployment["desired_replicas"]
        for deployment in workloads["deployments"]
    )
    success = rollout_error is None and application_ready
    return {
        "success": success,
        "cluster_name": cluster_name,
        "namespace": namespace,
        "deployment_status": "ready" if success else "not-ready",
        "apply_output": apply_output,
        "error": rollout_error
        or (None if application_ready else "Application deployment is not ready."),
        "deployments": workloads["deployments"],
        "pods": workloads["pods"],
        "services": workloads["services"],
    }
