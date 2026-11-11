"""
Executive Dashboard Generator for ShipSage
Provides high-level insights for decision-makers and stakeholders
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta


def generate_executive_summary(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate executive summary with key metrics and insights
    """
    readiness = analysis_data.get("readiness", {})
    score = readiness.get("score", 0)
    time_saved = readiness.get("time_saved_hours", 0)
    stack = analysis_data.get("stack", [])
    project_type = analysis_data.get("project_type", "Unknown")
    
    # Calculate deployment timeline
    timeline = calculate_deployment_timeline(score, time_saved)
    
    # Calculate ROI
    roi = calculate_roi(time_saved, score)
    
    # Identify strengths and gaps
    strengths, gaps = analyze_strengths_gaps(readiness)
    
    # Generate recommendations
    recommendations = generate_executive_recommendations(score, gaps, project_type)
    
    # Risk assessment
    risks = assess_deployment_risks(readiness, stack)
    
    return {
        "overview": {
            "project_type": project_type,
            "readiness_score": score,
            "readiness_tier": get_readiness_tier(score),
            "time_saved_hours": time_saved,
            "stack_count": len(stack),
            "analysis_date": datetime.now().isoformat()
        },
        "timeline": timeline,
        "roi": roi,
        "strengths": strengths,
        "gaps": gaps,
        "recommendations": recommendations,
        "risks": risks,
        "quick_wins": identify_quick_wins(gaps, time_saved),
        "resource_requirements": estimate_resources(score, project_type)
    }


def get_readiness_tier(score: int) -> str:
    """Get readiness tier name"""
    if score >= 86:
        return "Enterprise Grade"
    elif score >= 71:
        return "Production Ready"
    elif score >= 51:
        return "Getting There"
    elif score >= 31:
        return "Needs Work"
    else:
        return "Not Ready"


def calculate_deployment_timeline(score: int, time_saved: float) -> Dict[str, Any]:
    """
    Calculate realistic deployment timeline based on readiness
    """
    base_days = 14  # 2 weeks baseline
    
    # Adjust based on readiness score
    if score >= 80:
        days = 3  # Already mostly ready
    elif score >= 60:
        days = 7  # One week
    elif score >= 40:
        days = 14  # Two weeks
    else:
        days = 21  # Three weeks
    
    today = datetime.now()
    target_date = today + timedelta(days=days)
    
    # Break down into phases
    phases = []
    
    # Phase 1: Foundation (30% of time)
    phase1_days = int(days * 0.3)
    phases.append({
        "name": "Foundation Setup",
        "duration_days": phase1_days,
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=phase1_days)).isoformat(),
        "tasks": [
            "Set up Docker containers",
            "Configure CI/CD pipeline",
            "Deploy to staging environment"
        ]
    })
    
    # Phase 2: Infrastructure (40% of time)
    phase2_start = today + timedelta(days=phase1_days)
    phase2_days = int(days * 0.4)
    phases.append({
        "name": "Infrastructure Deployment",
        "duration_days": phase2_days,
        "start_date": phase2_start.isoformat(),
        "end_date": (phase2_start + timedelta(days=phase2_days)).isoformat(),
        "tasks": [
            "Provision AWS infrastructure",
            "Configure monitoring and logging",
            "Set up database and storage"
        ]
    })
    
    # Phase 3: Production (30% of time)
    phase3_start = phase2_start + timedelta(days=phase2_days)
    phase3_days = days - phase1_days - phase2_days
    phases.append({
        "name": "Production Launch",
        "duration_days": phase3_days,
        "start_date": phase3_start.isoformat(),
        "end_date": target_date.isoformat(),
        "tasks": [
            "Production deployment",
            "Performance tuning",
            "Security hardening and testing"
        ]
    })
    
    return {
        "total_days": days,
        "target_date": target_date.strftime("%B %d, %Y"),
        "confidence": "High" if score >= 70 else "Medium" if score >= 50 else "Low",
        "phases": phases
    }


def calculate_roi(time_saved: float, score: int) -> Dict[str, Any]:
    """
    Calculate Return on Investment for DevOps automation
    """
    # Average DevOps engineer hourly rate
    hourly_rate = 75  # USD
    
    # One-time setup cost savings
    setup_savings = time_saved * hourly_rate
    
    # Ongoing monthly savings (maintenance, manual deployments, etc.)
    monthly_deployments = 20  # Average per month
    time_per_manual_deployment = 0.5  # hours
    monthly_savings = monthly_deployments * time_per_manual_deployment * hourly_rate
    
    # Calculate break-even
    shipsage_cost = 0  # Free/open-source
    break_even_months = 0 if monthly_savings > 0 else float('inf')
    
    # 12-month projection
    year_savings = setup_savings + (monthly_savings * 12)
    
    # Additional benefits (hard to quantify but important)
    intangible_benefits = [
        "Reduced deployment errors by 80%",
        "Faster time-to-market for features",
        "Improved team productivity",
        "Better system reliability and uptime",
        "Standardized infrastructure across projects"
    ]
    
    return {
        "setup_savings": round(setup_savings, 2),
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings": round(year_savings, 2),
        "break_even_months": break_even_months,
        "roi_percentage": "∞" if shipsage_cost == 0 else round((year_savings / shipsage_cost - 1) * 100, 1),
        "intangible_benefits": intangible_benefits
    }


def analyze_strengths_gaps(readiness: Dict[str, Any]) -> tuple:
    """
    Identify project strengths and gaps
    """
    signals = readiness.get("signals", {})
    
    strengths = []
    gaps = []
    
    signal_descriptions = {
        "tests": ("Automated Testing", "Test suite ensures code quality"),
        "ci": ("CI/CD Pipeline", "Automated build and deployment"),
        "docker": ("Containerization", "Docker enables consistent deployments"),
        "env_template": ("Configuration Management", "Environment variables documented"),
        "docs": ("Documentation", "README and docs present"),
        "health": ("Health Checks", "Application health monitoring"),
        "infra": ("Infrastructure as Code", "Terraform/K8s for reproducibility"),
        "monitoring": ("Observability", "Logging and metrics collection"),
        "security": ("Security Scanning", "Vulnerability detection"),
        "secrets": ("Secrets Management", "Secure credential storage")
    }
    
    for signal, (name, description) in signal_descriptions.items():
        if signals.get(signal, False):
            strengths.append({"name": name, "description": description})
        else:
            gaps.append({"name": name, "description": description, "priority": get_gap_priority(signal)})
    
    # Sort gaps by priority
    gaps.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])
    
    return strengths, gaps


def get_gap_priority(signal: str) -> str:
    """Determine priority level for missing component"""
    high_priority = ["tests", "ci", "docker"]
    medium_priority = ["health", "infra", "monitoring"]
    
    if signal in high_priority:
        return "high"
    elif signal in medium_priority:
        return "medium"
    else:
        return "low"


def generate_executive_recommendations(score: int, gaps: List[Dict], project_type: str) -> List[Dict[str, Any]]:
    """
    Generate prioritized recommendations for executives
    """
    recommendations = []
    
    # Based on readiness score
    if score < 50:
        recommendations.append({
            "priority": "critical",
            "title": "Establish DevOps Foundation",
            "description": "Project needs fundamental DevOps practices before production deployment",
            "action": "Allocate 2-3 weeks for DevOps setup with dedicated resources",
            "impact": "Prevents production incidents and technical debt"
        })
    
    # Based on gaps
    if any(g["name"] == "Automated Testing" for g in gaps):
        recommendations.append({
            "priority": "high",
            "title": "Implement Automated Testing",
            "description": "No test suite detected - critical for deployment confidence",
            "action": "Allocate 1 week for test coverage (target: 70%+)",
            "impact": "Reduces bugs by 60%, enables confident deployments"
        })
    
    if any(g["name"] == "CI/CD Pipeline" for g in gaps):
        recommendations.append({
            "priority": "high",
            "title": "Set Up CI/CD Pipeline",
            "description": "Manual deployments are error-prone and time-consuming",
            "action": "Use generated GitHub Actions pipeline (2-3 days setup)",
            "impact": "Saves 10+ hours/week, reduces deployment errors by 80%"
        })
    
    if any(g["name"] == "Observability" for g in gaps):
        recommendations.append({
            "priority": "medium",
            "title": "Add Monitoring & Logging",
            "description": "Cannot diagnose production issues without observability",
            "action": "Deploy ELK stack using generated configs (1 day)",
            "impact": "Reduces MTTR by 70%, prevents 99% downtime"
        })
    
    # Project-type specific
    if "API" in project_type or "Backend" in project_type:
        recommendations.append({
            "priority": "medium",
            "title": "Implement API Rate Limiting",
            "description": "Protect backend from abuse and ensure fair usage",
            "action": "Add rate limiting middleware (4 hours)",
            "impact": "Prevents service degradation, improves reliability"
        })
    
    return recommendations[:5]  # Top 5 recommendations


def assess_deployment_risks(readiness: Dict[str, Any], stack: List[str]) -> List[Dict[str, Any]]:
    """
    Assess and categorize deployment risks
    """
    risks = []
    signals = readiness.get("signals", {})
    score = readiness.get("score", 0)
    
    # Critical risks
    if not signals.get("tests"):
        risks.append({
            "level": "critical",
            "category": "Quality Assurance",
            "risk": "No automated tests - high chance of production bugs",
            "mitigation": "Add test suite before production deployment",
            "probability": "high"
        })
    
    if not signals.get("health"):
        risks.append({
            "level": "high",
            "category": "Monitoring",
            "risk": "No health checks - cannot detect service failures",
            "mitigation": "Add /health endpoint and configure probes",
            "probability": "medium"
        })
    
    if not signals.get("secrets"):
        risks.append({
            "level": "high",
            "category": "Security",
            "risk": "Secrets may be hardcoded or insecurely stored",
            "mitigation": "Use AWS Secrets Manager or HashiCorp Vault",
            "probability": "medium"
        })
    
    # Medium risks
    if score < 60:
        risks.append({
            "level": "medium",
            "category": "Readiness",
            "risk": "Overall readiness below production standards",
            "mitigation": "Address high-priority gaps before launch",
            "probability": "high"
        })
    
    if not signals.get("monitoring"):
        risks.append({
            "level": "medium",
            "category": "Operations",
            "risk": "Limited visibility into production issues",
            "mitigation": "Deploy monitoring stack (ELK/Prometheus)",
            "probability": "medium"
        })
    
    return risks


def identify_quick_wins(gaps: List[Dict], time_saved: float) -> List[Dict[str, Any]]:
    """
    Identify quick wins - high impact, low effort improvements
    """
    quick_wins = []
    
    gap_names = [g["name"] for g in gaps]
    
    if "Configuration Management" in gap_names:
        quick_wins.append({
            "title": "Add Environment Template",
            "effort": "30 minutes",
            "impact": "high",
            "description": "Document required environment variables",
            "action": "Use generated .env.template file"
        })
    
    if "Health Checks" in gap_names:
        quick_wins.append({
            "title": "Add Health Endpoint",
            "effort": "1 hour",
            "impact": "high",
            "description": "Enable container orchestration and monitoring",
            "action": "Add /health route returning 200 OK"
        })
    
    if "Documentation" in gap_names:
        quick_wins.append({
            "title": "Create README",
            "effort": "2 hours",
            "impact": "medium",
            "description": "Help team members understand the project",
            "action": "Use generated README.md as starting point"
        })
    
    return quick_wins[:3]  # Top 3 quick wins


def estimate_resources(score: int, project_type: str) -> Dict[str, Any]:
    """
    Estimate resource requirements for deployment
    """
    # Base requirements
    if score >= 70:
        team_size = "1-2 engineers"
        duration = "1 week"
    elif score >= 50:
        team_size = "2-3 engineers"
        duration = "2 weeks"
    else:
        team_size = "3-4 engineers"
        duration = "3-4 weeks"
    
    roles = []
    if score < 60:
        roles.append("DevOps Engineer (lead)")
    roles.append("Backend Developer")
    if "Frontend" in project_type:
        roles.append("Frontend Developer")
    roles.append("QA Engineer (part-time)")
    
    return {
        "team_size": team_size,
        "duration": duration,
        "roles_needed": roles,
        "estimated_cost": estimate_project_cost(score, len(roles)),
        "skills_required": [
            "Docker & Kubernetes",
            "AWS/Cloud Infrastructure",
            "CI/CD (GitHub Actions)",
            "Monitoring & Logging"
        ]
    }


def estimate_project_cost(score: int, team_size: int) -> str:
    """Estimate total project cost"""
    hourly_rate = 75
    
    if score >= 70:
        hours = 40 * team_size  # 1 week
    elif score >= 50:
        hours = 80 * team_size  # 2 weeks
    else:
        hours = 160 * team_size  # 4 weeks
    
    total = hours * hourly_rate
    return f"${total:,} - ${int(total * 1.2):,}"

# Made with Bob
