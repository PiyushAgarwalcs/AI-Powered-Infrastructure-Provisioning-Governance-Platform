"""
Configuration Validator Module
Validates generated Kubernetes manifests (YAML), Terraform configurations (HCL),
Dockerfiles, and Docker Compose configurations against structural, syntax, and schema standards.
"""
import yaml
import re
from typing import Dict, Any, List


def validate_kubernetes_manifests(yaml_content: str, require_deployment_and_service: bool = False) -> Dict[str, Any]:
    """
    Validate that Kubernetes manifests are syntactically valid YAML and contain
    required Kubernetes resource structures (apiVersion, kind, metadata, spec).
    """
    errors: List[str] = []
    kinds: List[str] = []
    names: List[str] = []
    documents: List[dict] = []

    if not yaml_content or not yaml_content.strip():
        return {
            "valid": False,
            "document_count": 0,
            "kinds": [],
            "names": [],
            "errors": ["Kubernetes manifest content is empty"]
        }

    try:
        loaded = list(yaml.safe_load_all(yaml_content))
    except yaml.YAMLError as e:
        return {
            "valid": False,
            "document_count": 0,
            "kinds": [],
            "names": [],
            "errors": [f"YAML parsing error: {str(e)}"]
        }

    for idx, doc in enumerate(loaded):
        if not doc:
            continue
        if not isinstance(doc, dict):
            errors.append(f"Document {idx + 1} is not a valid Kubernetes mapping object")
            continue

        api_version = doc.get("apiVersion")
        kind = doc.get("kind")
        metadata = doc.get("metadata", {})
        name = metadata.get("name") if isinstance(metadata, dict) else None

        if not api_version:
            errors.append(f"Document {idx + 1} ({kind or 'Unknown'}) is missing 'apiVersion'")
        if not kind:
            errors.append(f"Document {idx + 1} is missing 'kind'")
        else:
            kinds.append(kind)

        if not name:
            errors.append(f"Document {idx + 1} ({kind or 'Unknown'}) is missing 'metadata.name'")
        else:
            names.append(name)

        # Specific structural checks for Deployments and Services
        if kind == "Deployment":
            spec = doc.get("spec", {})
            if "replicas" not in spec:
                errors.append(f"Deployment '{name}' missing 'spec.replicas'")
            template = spec.get("template", {})
            containers = template.get("spec", {}).get("containers", [])
            if not containers:
                errors.append(f"Deployment '{name}' template spec has no containers defined")

        elif kind == "Service":
            spec = doc.get("spec", {})
            if "ports" not in spec or not spec["ports"]:
                errors.append(f"Service '{name}' has no ports defined")

        documents.append(doc)

    if require_deployment_and_service:
        has_deployment = "Deployment" in kinds
        has_service = "Service" in kinds
        if not has_deployment:
            errors.append("Manifests do not contain a Deployment resource")
        if not has_service:
            errors.append("Manifests do not contain a Service resource")

    return {
        "valid": len(errors) == 0,
        "document_count": len(documents),
        "kinds": kinds,
        "names": names,
        "errors": errors
    }


def validate_terraform_code(tf_content: str, require_provider: bool = False) -> Dict[str, Any]:
    """
    Validate basic HCL structure, bracket balance, and required Terraform blocks.
    """
    errors: List[str] = []

    if not tf_content or not tf_content.strip():
        return {"valid": False, "errors": ["Terraform content is empty"]}

    # Check balanced braces
    open_braces = tf_content.count("{")
    close_braces = tf_content.count("}")
    if open_braces != close_braces:
        errors.append(f"Mismatched curly braces: {open_braces} open vs {close_braces} close (Unclosed block)")

    # Check balanced brackets
    open_brackets = tf_content.count("[")
    close_brackets = tf_content.count("]")
    if open_brackets != close_brackets:
        errors.append(f"Mismatched square brackets: {open_brackets} open vs {close_brackets} close")

    # Check essential blocks if required
    if require_provider:
        if "terraform {" not in tf_content and "terraform{" not in tf_content:
            errors.append("Missing 'terraform' block")
        if 'provider "aws"' not in tf_content and "provider 'aws'" not in tf_content and "provider aws" not in tf_content:
            errors.append("Missing AWS provider block")

    if "resource " not in tf_content and "module " not in tf_content and "variable " not in tf_content and "output " not in tf_content:
        errors.append("No Terraform resources, modules, variables, or outputs defined")

    return {
        "valid": len(errors) == 0,
        "resource_count": len(re.findall(r'resource\s+"[^"]+"\s+"[^"]+"', tf_content)),
        "module_count": len(re.findall(r'module\s+"[^"]+"', tf_content)),
        "output_count": len(re.findall(r'output\s+"[^"]+"', tf_content)),
        "errors": errors
    }


def validate_dockerfile_syntax(dockerfile_content: str) -> Dict[str, Any]:
    """
    Validate that a Dockerfile contains essential instructions.
    """
    errors: List[str] = []

    if not dockerfile_content or not dockerfile_content.strip():
        return {"valid": False, "errors": ["Dockerfile content is empty"]}

    lines = [line.strip() for line in dockerfile_content.splitlines() if line.strip() and not line.strip().startswith("#")]

    has_from = any(l.startswith("FROM ") for l in lines)
    has_workdir = any(l.startswith("WORKDIR ") for l in lines)
    has_cmd_or_entrypoint = any(l.startswith("CMD ") or l.startswith("ENTRYPOINT ") for l in lines)

    if not has_from:
        errors.append("Missing FROM instruction")
    if not has_workdir:
        errors.append("Missing WORKDIR instruction")
    if not has_cmd_or_entrypoint:
        errors.append("Missing CMD or ENTRYPOINT instruction")

    return {
        "valid": len(errors) == 0,
        "stage_count": len([l for l in lines if l.startswith("FROM ")]),
        "errors": errors
    }


def validate_compose_syntax(compose_content: str) -> Dict[str, Any]:
    """
    Validate that Docker Compose content is valid YAML and contains services.
    """
    errors: List[str] = []
    if not compose_content or not compose_content.strip():
        return {"valid": False, "errors": ["Compose content is empty"]}
    try:
        data = yaml.safe_load(compose_content)
        if not isinstance(data, dict):
            return {"valid": False, "errors": ["Compose content is not a mapping object"]}
        if "services" not in data:
            errors.append("Missing 'services' key in compose file")
        return {
            "valid": len(errors) == 0,
            "service_count": len(data.get("services", {})) if isinstance(data.get("services"), dict) else 0,
            "errors": errors
        }
    except Exception as e:
        return {"valid": False, "errors": [f"YAML error: {str(e)}"]}


def validate_all_spec_configurations(configs: Dict[str, str]) -> Dict[str, Any]:
    """
    Run validators across all generated configuration components.
    """
    results: Dict[str, Any] = {}
    if "kubernetes" in configs and configs["kubernetes"]:
        results["kubernetes"] = validate_kubernetes_manifests(configs["kubernetes"], require_deployment_and_service=True)
    if "aws_terraform" in configs and configs["aws_terraform"]:
        results["aws_terraform"] = validate_terraform_code(configs["aws_terraform"])
    if "dockerfile" in configs and configs["dockerfile"]:
        results["dockerfile"] = validate_dockerfile_syntax(configs["dockerfile"])
    if "compose" in configs and configs["compose"]:
        results["compose"] = validate_compose_syntax(configs["compose"])
    return results
