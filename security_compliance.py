"""
Security & Compliance Dashboard
Provides security assessment, compliance checks, and vulnerability analysis
"""

from typing import Dict, List, Any
import re


def generate_security_dashboard(
    analysis: Dict[str, Any],
    stack: List[str],
    configs: Dict[str, str]
) -> Dict[str, Any]:
    """
    Generate comprehensive security and compliance dashboard.
    
    Args:
        analysis: Repository analysis data
        stack: Technology stack
        configs: Generated configuration files
        
    Returns:
        Security dashboard with assessments and recommendations
    """
    
    readiness = analysis.get("readiness", {})
    signals = readiness.get("signals", {})
    
    return {
        "security_score": _calculate_security_score(signals, configs),
        "compliance_status": _assess_compliance(stack, configs),
        "vulnerabilities": _identify_vulnerabilities(configs, stack),
        "security_recommendations": _generate_security_recommendations(signals, stack),
        "compliance_checklist": _generate_compliance_checklist(stack),
        "security_best_practices": _get_security_best_practices(stack),
        "audit_trail": _generate_audit_requirements(stack)
    }


def _calculate_security_score(signals: Dict[str, bool], configs: Dict[str, str]) -> Dict[str, Any]:
    """Calculate overall security score"""
    
    score = 0
    max_score = 100
    checks = []
    
    # Check 1: Environment variables (20 points)
    if signals.get("env_template"):
        score += 20
        checks.append({
            "name": "Environment Configuration",
            "status": "pass",
            "points": 20,
            "description": "Environment template found - secrets management in place"
        })
    else:
        checks.append({
            "name": "Environment Configuration",
            "status": "fail",
            "points": 0,
            "description": "No environment template - secrets may be hardcoded"
        })
    
    # Check 2: Container security (15 points)
    dockerfile = configs.get("dockerfile", "")
    if "USER" in dockerfile and "USER root" not in dockerfile:
        score += 15
        checks.append({
            "name": "Container User Privileges",
            "status": "pass",
            "points": 15,
            "description": "Non-root user configured in Docker"
        })
    else:
        checks.append({
            "name": "Container User Privileges",
            "status": "fail",
            "points": 0,
            "description": "Container may run as root - security risk"
        })
    
    # Check 3: Network policies (15 points)
    kubernetes = configs.get("kubernetes", "")
    if "NetworkPolicy" in kubernetes:
        score += 15
        checks.append({
            "name": "Network Policies",
            "status": "pass",
            "points": 15,
            "description": "Network policies defined in Kubernetes"
        })
    else:
        checks.append({
            "name": "Network Policies",
            "status": "warning",
            "points": 7,
            "description": "No network policies - consider adding for pod isolation"
        })
        score += 7
    
    # Check 4: HTTPS/TLS (15 points)
    if "ssl" in configs.get("env_config", "").lower() or "tls" in kubernetes.lower():
        score += 15
        checks.append({
            "name": "TLS/SSL Configuration",
            "status": "pass",
            "points": 15,
            "description": "TLS/SSL configuration detected"
        })
    else:
        checks.append({
            "name": "TLS/SSL Configuration",
            "status": "fail",
            "points": 0,
            "description": "No TLS/SSL configuration - data transmitted in plaintext"
        })
    
    # Check 5: Security scanning in CI/CD (15 points)
    cicd = configs.get("cicd", "")
    if "trivy" in cicd.lower() or "snyk" in cicd.lower() or "security" in cicd.lower():
        score += 15
        checks.append({
            "name": "Security Scanning",
            "status": "pass",
            "points": 15,
            "description": "Security scanning integrated in CI/CD"
        })
    else:
        checks.append({
            "name": "Security Scanning",
            "status": "fail",
            "points": 0,
            "description": "No security scanning in pipeline"
        })
    
    # Check 6: Resource limits (10 points)
    if "limits:" in kubernetes and "requests:" in kubernetes:
        score += 10
        checks.append({
            "name": "Resource Limits",
            "status": "pass",
            "points": 10,
            "description": "Resource limits configured - prevents resource exhaustion"
        })
    else:
        checks.append({
            "name": "Resource Limits",
            "status": "warning",
            "points": 5,
            "description": "Resource limits not fully configured"
        })
        score += 5
    
    # Check 7: Health checks (10 points)
    if signals.get("health"):
        score += 10
        checks.append({
            "name": "Health Checks",
            "status": "pass",
            "points": 10,
            "description": "Health check endpoints implemented"
        })
    else:
        checks.append({
            "name": "Health Checks",
            "status": "fail",
            "points": 0,
            "description": "No health checks - impacts availability monitoring"
        })
    
    # Determine security level
    if score >= 80:
        level = "excellent"
        color = "#10b981"
        message = "Strong security posture"
    elif score >= 60:
        level = "good"
        color = "#3b82f6"
        message = "Good security with room for improvement"
    elif score >= 40:
        level = "fair"
        color = "#f59e0b"
        message = "Fair security - several improvements needed"
    else:
        level = "poor"
        color = "#ef4444"
        message = "Poor security - immediate action required"
    
    return {
        "score": score,
        "max_score": max_score,
        "percentage": int((score / max_score) * 100),
        "level": level,
        "color": color,
        "message": message,
        "checks": checks,
        "passed": sum(1 for c in checks if c["status"] == "pass"),
        "failed": sum(1 for c in checks if c["status"] == "fail"),
        "warnings": sum(1 for c in checks if c["status"] == "warning")
    }


def _assess_compliance(stack: List[str], configs: Dict[str, str]) -> Dict[str, Any]:
    """Assess compliance with various standards"""
    
    frameworks = {
        "SOC 2": _check_soc2_compliance(configs),
        "GDPR": _check_gdpr_compliance(configs),
        "HIPAA": _check_hipaa_compliance(configs, stack),
        "PCI DSS": _check_pci_compliance(configs),
        "ISO 27001": _check_iso27001_compliance(configs)
    }
    
    overall_compliance = sum(f["score"] for f in frameworks.values()) / len(frameworks)
    
    return {
        "overall_score": int(overall_compliance),
        "frameworks": frameworks,
        "compliant_count": sum(1 for f in frameworks.values() if f["score"] >= 70),
        "total_frameworks": len(frameworks)
    }


def _check_soc2_compliance(configs: Dict[str, str]) -> Dict[str, Any]:
    """Check SOC 2 compliance requirements"""
    score = 0
    requirements = []
    
    # Logging and monitoring
    if configs.get("monitoring"):
        score += 30
        requirements.append({"name": "Logging & Monitoring", "status": "compliant"})
    else:
        requirements.append({"name": "Logging & Monitoring", "status": "non-compliant"})
    
    # Access controls
    kubernetes = configs.get("kubernetes", "")
    if "ServiceAccount" in kubernetes or "RBAC" in kubernetes:
        score += 25
        requirements.append({"name": "Access Controls", "status": "compliant"})
    else:
        requirements.append({"name": "Access Controls", "status": "non-compliant"})
    
    # Encryption
    if "tls" in configs.get("env_config", "").lower():
        score += 25
        requirements.append({"name": "Data Encryption", "status": "compliant"})
    else:
        requirements.append({"name": "Data Encryption", "status": "non-compliant"})
    
    # Backup and recovery
    terraform = configs.get("aws_terraform", "")
    if "backup" in terraform.lower():
        score += 20
        requirements.append({"name": "Backup & Recovery", "status": "compliant"})
    else:
        requirements.append({"name": "Backup & Recovery", "status": "partial"})
        score += 10
    
    return {
        "score": score,
        "requirements": requirements,
        "status": "compliant" if score >= 70 else "partial" if score >= 50 else "non-compliant"
    }


def _check_gdpr_compliance(configs: Dict[str, str]) -> Dict[str, Any]:
    """Check GDPR compliance requirements"""
    score = 0
    requirements = []
    
    # Data encryption
    if "encryption" in configs.get("aws_terraform", "").lower():
        score += 35
        requirements.append({"name": "Data Encryption at Rest", "status": "compliant"})
    else:
        requirements.append({"name": "Data Encryption at Rest", "status": "non-compliant"})
    
    # Access logging
    if configs.get("monitoring"):
        score += 35
        requirements.append({"name": "Access Logging", "status": "compliant"})
    else:
        requirements.append({"name": "Access Logging", "status": "non-compliant"})
    
    # Data retention
    score += 15  # Assume basic retention
    requirements.append({"name": "Data Retention Policies", "status": "partial"})
    
    # Right to deletion
    score += 15  # Assume basic capability
    requirements.append({"name": "Data Deletion Capability", "status": "partial"})
    
    return {
        "score": score,
        "requirements": requirements,
        "status": "compliant" if score >= 70 else "partial" if score >= 50 else "non-compliant"
    }


def _check_hipaa_compliance(configs: Dict[str, str], stack: List[str]) -> Dict[str, Any]:
    """Check HIPAA compliance requirements"""
    score = 0
    requirements = []
    
    # Only relevant if healthcare-related
    is_healthcare = any(term in str(stack).lower() for term in ["health", "medical", "patient"])
    
    if not is_healthcare:
        return {
            "score": 0,
            "requirements": [{"name": "Not Applicable", "status": "n/a"}],
            "status": "n/a"
        }
    
    # Encryption
    terraform = configs.get("aws_terraform", "")
    if "encryption" in terraform.lower():
        score += 40
        requirements.append({"name": "PHI Encryption", "status": "compliant"})
    else:
        requirements.append({"name": "PHI Encryption", "status": "non-compliant"})
    
    # Audit controls
    if configs.get("monitoring"):
        score += 30
        requirements.append({"name": "Audit Controls", "status": "compliant"})
    else:
        requirements.append({"name": "Audit Controls", "status": "non-compliant"})
    
    # Access controls
    score += 15  # Assume basic controls
    requirements.append({"name": "Access Controls", "status": "partial"})
    
    # Backup
    if "backup" in terraform.lower():
        score += 15
        requirements.append({"name": "Data Backup", "status": "compliant"})
    else:
        requirements.append({"name": "Data Backup", "status": "non-compliant"})
    
    return {
        "score": score,
        "requirements": requirements,
        "status": "compliant" if score >= 70 else "partial" if score >= 50 else "non-compliant"
    }


def _check_pci_compliance(configs: Dict[str, str]) -> Dict[str, Any]:
    """Check PCI DSS compliance requirements"""
    score = 0
    requirements = []
    
    # Network segmentation
    kubernetes = configs.get("kubernetes", "")
    if "NetworkPolicy" in kubernetes:
        score += 25
        requirements.append({"name": "Network Segmentation", "status": "compliant"})
    else:
        requirements.append({"name": "Network Segmentation", "status": "non-compliant"})
    
    # Encryption
    if "tls" in configs.get("env_config", "").lower():
        score += 25
        requirements.append({"name": "Data Transmission Security", "status": "compliant"})
    else:
        requirements.append({"name": "Data Transmission Security", "status": "non-compliant"})
    
    # Access control
    score += 15  # Assume basic controls
    requirements.append({"name": "Access Control", "status": "partial"})
    
    # Monitoring
    if configs.get("monitoring"):
        score += 20
        requirements.append({"name": "Security Monitoring", "status": "compliant"})
    else:
        requirements.append({"name": "Security Monitoring", "status": "non-compliant"})
    
    # Vulnerability management
    cicd = configs.get("cicd", "")
    if "security" in cicd.lower() or "scan" in cicd.lower():
        score += 15
        requirements.append({"name": "Vulnerability Scanning", "status": "compliant"})
    else:
        requirements.append({"name": "Vulnerability Scanning", "status": "non-compliant"})
    
    return {
        "score": score,
        "requirements": requirements,
        "status": "compliant" if score >= 70 else "partial" if score >= 50 else "non-compliant"
    }


def _check_iso27001_compliance(configs: Dict[str, str]) -> Dict[str, Any]:
    """Check ISO 27001 compliance requirements"""
    score = 0
    requirements = []
    
    # Information security policy
    score += 15  # Assume basic policy
    requirements.append({"name": "Security Policy", "status": "partial"})
    
    # Access control
    kubernetes = configs.get("kubernetes", "")
    if "ServiceAccount" in kubernetes:
        score += 20
        requirements.append({"name": "Access Control", "status": "compliant"})
    else:
        requirements.append({"name": "Access Control", "status": "partial"})
        score += 10
    
    # Cryptography
    if "encryption" in configs.get("aws_terraform", "").lower():
        score += 20
        requirements.append({"name": "Cryptographic Controls", "status": "compliant"})
    else:
        requirements.append({"name": "Cryptographic Controls", "status": "non-compliant"})
    
    # Operations security
    if configs.get("monitoring"):
        score += 20
        requirements.append({"name": "Operations Security", "status": "compliant"})
    else:
        requirements.append({"name": "Operations Security", "status": "non-compliant"})
    
    # Incident management
    score += 10  # Assume basic capability
    requirements.append({"name": "Incident Management", "status": "partial"})
    
    # Business continuity
    terraform = configs.get("aws_terraform", "")
    if "backup" in terraform.lower():
        score += 15
        requirements.append({"name": "Business Continuity", "status": "compliant"})
    else:
        requirements.append({"name": "Business Continuity", "status": "partial"})
        score += 7
    
    return {
        "score": score,
        "requirements": requirements,
        "status": "compliant" if score >= 70 else "partial" if score >= 50 else "non-compliant"
    }


def _identify_vulnerabilities(configs: Dict[str, str], stack: List[str]) -> List[Dict[str, Any]]:
    """Identify potential vulnerabilities"""
    vulnerabilities = []
    
    dockerfile = configs.get("dockerfile", "")
    kubernetes = configs.get("kubernetes", "")
    cicd = configs.get("cicd", "")
    
    # Check for root user in Docker
    if "USER root" in dockerfile or "USER" not in dockerfile:
        vulnerabilities.append({
            "severity": "high",
            "category": "Container Security",
            "title": "Container Running as Root",
            "description": "Container may run with root privileges, increasing attack surface",
            "remediation": "Add 'USER <non-root-user>' directive in Dockerfile",
            "cve_risk": "Privilege escalation attacks"
        })
    
    # Check for missing security context
    if "securityContext" not in kubernetes:
        vulnerabilities.append({
            "severity": "medium",
            "category": "Kubernetes Security",
            "title": "Missing Security Context",
            "description": "Pods lack security context configuration",
            "remediation": "Add securityContext with runAsNonRoot: true and readOnlyRootFilesystem: true",
            "cve_risk": "Container breakout"
        })
    
    # Check for missing network policies
    if "NetworkPolicy" not in kubernetes:
        vulnerabilities.append({
            "severity": "medium",
            "category": "Network Security",
            "title": "No Network Policies",
            "description": "Pods can communicate freely without restrictions",
            "remediation": "Implement NetworkPolicy resources to restrict pod-to-pod communication",
            "cve_risk": "Lateral movement in cluster"
        })
    
    # Check for missing secrets management
    if ".env" in dockerfile or "ENV" in dockerfile:
        vulnerabilities.append({
            "severity": "high",
            "category": "Secrets Management",
            "title": "Hardcoded Secrets Risk",
            "description": "Environment variables may contain hardcoded secrets",
            "remediation": "Use Kubernetes Secrets or external secret management (AWS Secrets Manager, HashiCorp Vault)",
            "cve_risk": "Credential exposure"
        })
    
    # Check for missing image scanning
    if "trivy" not in cicd.lower() and "snyk" not in cicd.lower():
        vulnerabilities.append({
            "severity": "high",
            "category": "Supply Chain Security",
            "title": "No Container Image Scanning",
            "description": "Container images not scanned for vulnerabilities",
            "remediation": "Add Trivy or Snyk scanning to CI/CD pipeline",
            "cve_risk": "Known CVEs in dependencies"
        })
    
    # Check for missing resource limits
    if "limits:" not in kubernetes:
        vulnerabilities.append({
            "severity": "low",
            "category": "Resource Management",
            "title": "Missing Resource Limits",
            "description": "Pods can consume unlimited resources",
            "remediation": "Set CPU and memory limits in pod specifications",
            "cve_risk": "Resource exhaustion / DoS"
        })
    
    return vulnerabilities


def _generate_security_recommendations(signals: Dict[str, bool], stack: List[str]) -> List[Dict[str, Any]]:
    """Generate security recommendations"""
    recommendations = []
    
    if not signals.get("security"):
        recommendations.append({
            "priority": "critical",
            "title": "Implement Security Scanning",
            "description": "Add automated security scanning to your CI/CD pipeline",
            "actions": [
                "Integrate Trivy for container image scanning",
                "Add SAST tools like SonarQube or Semgrep",
                "Enable dependency vulnerability scanning",
                "Set up automated security alerts"
            ],
            "impact": "Detect vulnerabilities before production deployment"
        })
    
    if not signals.get("env_template"):
        recommendations.append({
            "priority": "high",
            "title": "Implement Secrets Management",
            "description": "Use proper secrets management instead of hardcoded values",
            "actions": [
                "Create Kubernetes Secrets for sensitive data",
                "Consider AWS Secrets Manager or HashiCorp Vault",
                "Never commit secrets to version control",
                "Rotate secrets regularly"
            ],
            "impact": "Prevent credential exposure and unauthorized access"
        })
    
    recommendations.append({
        "priority": "high",
        "title": "Enable TLS/SSL Everywhere",
        "description": "Encrypt all data in transit",
        "actions": [
            "Configure TLS termination at load balancer",
            "Use cert-manager for automatic certificate management",
            "Enforce HTTPS redirects",
            "Enable TLS for internal service communication"
        ],
        "impact": "Protect data from man-in-the-middle attacks"
    })
    
    recommendations.append({
        "priority": "medium",
        "title": "Implement Network Segmentation",
        "description": "Restrict network access between services",
        "actions": [
            "Create Kubernetes NetworkPolicies",
            "Use separate namespaces for different environments",
            "Implement zero-trust networking",
            "Restrict egress traffic"
        ],
        "impact": "Limit blast radius of security breaches"
    })
    
    recommendations.append({
        "priority": "medium",
        "title": "Enable Audit Logging",
        "description": "Track all access and changes for compliance",
        "actions": [
            "Enable Kubernetes audit logging",
            "Configure AWS CloudTrail",
            "Set up centralized log aggregation",
            "Implement log retention policies"
        ],
        "impact": "Meet compliance requirements and detect security incidents"
    })
    
    return recommendations


def _generate_compliance_checklist(stack: List[str]) -> List[Dict[str, Any]]:
    """Generate compliance checklist"""
    return [
        {
            "category": "Data Protection",
            "items": [
                {"task": "Encrypt data at rest", "required": True},
                {"task": "Encrypt data in transit", "required": True},
                {"task": "Implement data retention policies", "required": True},
                {"task": "Enable data backup and recovery", "required": True}
            ]
        },
        {
            "category": "Access Control",
            "items": [
                {"task": "Implement RBAC", "required": True},
                {"task": "Use strong authentication", "required": True},
                {"task": "Enable MFA for admin access", "required": True},
                {"task": "Regular access reviews", "required": False}
            ]
        },
        {
            "category": "Monitoring & Logging",
            "items": [
                {"task": "Enable audit logging", "required": True},
                {"task": "Set up security monitoring", "required": True},
                {"task": "Configure alerting", "required": True},
                {"task": "Log retention (90+ days)", "required": True}
            ]
        },
        {
            "category": "Vulnerability Management",
            "items": [
                {"task": "Regular security scanning", "required": True},
                {"task": "Patch management process", "required": True},
                {"task": "Dependency updates", "required": True},
                {"task": "Penetration testing", "required": False}
            ]
        }
    ]


def _get_security_best_practices(stack: List[str]) -> List[Dict[str, Any]]:
    """Get security best practices"""
    return [
        {
            "category": "Container Security",
            "practices": [
                "Use minimal base images (Alpine, distroless)",
                "Run containers as non-root user",
                "Use read-only root filesystem",
                "Scan images for vulnerabilities",
                "Sign and verify images"
            ]
        },
        {
            "category": "Kubernetes Security",
            "practices": [
                "Enable Pod Security Standards",
                "Use NetworkPolicies for segmentation",
                "Implement RBAC with least privilege",
                "Enable audit logging",
                "Use secrets for sensitive data"
            ]
        },
        {
            "category": "Application Security",
            "practices": [
                "Input validation and sanitization",
                "Use parameterized queries (SQL injection prevention)",
                "Implement rate limiting",
                "Enable CORS properly",
                "Use security headers (CSP, HSTS, etc.)"
            ]
        },
        {
            "category": "Infrastructure Security",
            "practices": [
                "Enable encryption at rest and in transit",
                "Use private subnets for databases",
                "Implement WAF for web applications",
                "Regular security patching",
                "Backup and disaster recovery"
            ]
        }
    ]


def _generate_audit_requirements(stack: List[str]) -> Dict[str, Any]:
    """Generate audit trail requirements"""
    return {
        "required_logs": [
            "Authentication attempts (success/failure)",
            "Authorization decisions",
            "Data access and modifications",
            "Configuration changes",
            "Security events and alerts"
        ],
        "retention_period": "90 days minimum (365 days recommended)",
        "log_protection": [
            "Immutable log storage",
            "Encrypted log transmission",
            "Access controls on logs",
            "Regular log reviews"
        ],
        "compliance_mapping": {
            "SOC 2": "Logging and monitoring controls",
            "GDPR": "Article 30 - Records of processing activities",
            "HIPAA": "§164.312(b) - Audit controls",
            "PCI DSS": "Requirement 10 - Track and monitor all access"
        }
    }

# Made with Bob
