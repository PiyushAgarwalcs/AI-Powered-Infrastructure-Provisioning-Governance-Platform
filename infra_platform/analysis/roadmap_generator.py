"""
Deployment Roadmap Generator
Generates visual deployment roadmaps with milestones, dependencies, and timelines
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


def generate_deployment_roadmap(
    readiness_score: int,
    project_type: str,
    stack: List[str],
    signals: Dict[str, bool]
) -> Dict[str, Any]:
    """
    Generate a comprehensive deployment roadmap with weekly breakdown,
    milestones, dependencies, and team assignments.
    
    Args:
        readiness_score: Current readiness score (0-100)
        project_type: Type of project (Backend API, Frontend, etc.)
        stack: List of technologies in the stack
        signals: Dictionary of detected signals
        
    Returns:
        Dictionary containing roadmap data
    """
    
    # Calculate timeline based on readiness
    total_weeks = _calculate_timeline_weeks(readiness_score)
    
    # Generate weekly breakdown
    weeks = _generate_weekly_breakdown(
        total_weeks, readiness_score, project_type, stack, signals
    )
    
    # Identify milestones
    milestones = _identify_milestones(weeks, readiness_score)
    
    # Map dependencies
    dependencies = _map_dependencies(weeks)
    
    # Assign teams
    team_assignments = _assign_teams(weeks, project_type)
    
    # Calculate progress metrics
    progress = _calculate_progress_metrics(weeks, readiness_score)
    
    return {
        "total_weeks": total_weeks,
        "start_date": datetime.now().strftime("%B %d, %Y"),
        "target_date": (datetime.now() + timedelta(weeks=total_weeks)).strftime("%B %d, %Y"),
        "weeks": weeks,
        "milestones": milestones,
        "dependencies": dependencies,
        "team_assignments": team_assignments,
        "progress": progress,
        "critical_path": _identify_critical_path(weeks)
    }


def _calculate_timeline_weeks(readiness_score: int) -> int:
    """Calculate total weeks needed based on readiness score"""
    if readiness_score >= 80:
        return 2  # 2 weeks for highly ready projects
    elif readiness_score >= 60:
        return 3  # 3 weeks for moderately ready
    elif readiness_score >= 40:
        return 4  # 4 weeks for projects needing work
    else:
        return 6  # 6 weeks for projects needing significant work


def _generate_weekly_breakdown(
    total_weeks: int,
    readiness_score: int,
    project_type: str,
    stack: List[str],
    signals: Dict[str, bool]
) -> List[Dict[str, Any]]:
    """Generate detailed weekly breakdown of tasks"""
    
    weeks = []
    current_date = datetime.now()
    
    # Week 1: Foundation & Setup
    week1_tasks = [
        {"name": "Environment Setup", "status": "ready" if signals.get("env_template") else "pending", "hours": 4},
        {"name": "Docker Configuration", "status": "ready" if signals.get("docker") else "pending", "hours": 6},
        {"name": "CI/CD Pipeline Setup", "status": "ready" if signals.get("ci") else "pending", "hours": 8},
        {"name": "Database Schema Review", "status": "pending", "hours": 4}
    ]
    
    weeks.append({
        "week_number": 1,
        "name": "Foundation & Setup",
        "start_date": current_date.strftime("%b %d"),
        "end_date": (current_date + timedelta(days=6)).strftime("%b %d"),
        "tasks": week1_tasks,
        "total_hours": sum(t["hours"] for t in week1_tasks),
        "completion": _calculate_week_completion(week1_tasks),
        "focus": "Infrastructure foundation and development environment",
        "deliverables": ["Docker containers", "CI/CD pipeline", "Environment configs"],
        "blockers": [] if signals.get("docker") and signals.get("ci") else ["Missing Docker or CI/CD setup"]
    })
    
    # Week 2: Core Infrastructure
    current_date += timedelta(weeks=1)
    week2_tasks = [
        {"name": "Kubernetes Deployment", "status": "pending", "hours": 10},
        {"name": "Load Balancer Config", "status": "pending", "hours": 4},
        {"name": "SSL/TLS Setup", "status": "pending", "hours": 3},
        {"name": "Monitoring Integration", "status": "pending", "hours": 5}
    ]
    
    weeks.append({
        "week_number": 2,
        "name": "Core Infrastructure",
        "start_date": current_date.strftime("%b %d"),
        "end_date": (current_date + timedelta(days=6)).strftime("%b %d"),
        "tasks": week2_tasks,
        "total_hours": sum(t["hours"] for t in week2_tasks),
        "completion": 0,
        "focus": "Production infrastructure and orchestration",
        "deliverables": ["K8s manifests", "Load balancer", "SSL certificates", "Monitoring"],
        "blockers": ["Depends on Week 1 completion"]
    })
    
    if total_weeks >= 3:
        # Week 3: Testing & Security
        current_date += timedelta(weeks=1)
        week3_tasks = [
            {"name": "Integration Testing", "status": "ready" if signals.get("tests") else "pending", "hours": 8},
            {"name": "Security Scanning", "status": "pending", "hours": 4},
            {"name": "Performance Testing", "status": "pending", "hours": 6},
            {"name": "Backup Configuration", "status": "pending", "hours": 3}
        ]
        
        weeks.append({
            "week_number": 3,
            "name": "Testing & Security",
            "start_date": current_date.strftime("%b %d"),
            "end_date": (current_date + timedelta(days=6)).strftime("%b %d"),
            "tasks": week3_tasks,
            "total_hours": sum(t["hours"] for t in week3_tasks),
            "completion": 0,
            "focus": "Quality assurance and security hardening",
            "deliverables": ["Test reports", "Security audit", "Backup strategy"],
            "blockers": ["Depends on Week 2 infrastructure"]
        })
    
    if total_weeks >= 4:
        # Week 4: Optimization & Documentation
        current_date += timedelta(weeks=1)
        week4_tasks = [
            {"name": "Performance Optimization", "status": "pending", "hours": 8},
            {"name": "Documentation", "status": "ready" if signals.get("docs") else "pending", "hours": 6},
            {"name": "Runbook Creation", "status": "pending", "hours": 4},
            {"name": "Team Training", "status": "pending", "hours": 4}
        ]
        
        weeks.append({
            "week_number": 4,
            "name": "Optimization & Docs",
            "start_date": current_date.strftime("%b %d"),
            "end_date": (current_date + timedelta(days=6)).strftime("%b %d"),
            "tasks": week4_tasks,
            "total_hours": sum(t["hours"] for t in week4_tasks),
            "completion": 0,
            "focus": "Performance tuning and knowledge transfer",
            "deliverables": ["Optimized configs", "Documentation", "Runbooks"],
            "blockers": []
        })
    
    if total_weeks >= 5:
        # Week 5: Staging Deployment
        current_date += timedelta(weeks=1)
        week5_tasks = [
            {"name": "Staging Environment Setup", "status": "pending", "hours": 6},
            {"name": "Data Migration Testing", "status": "pending", "hours": 8},
            {"name": "User Acceptance Testing", "status": "pending", "hours": 8},
            {"name": "Rollback Testing", "status": "pending", "hours": 4}
        ]
        
        weeks.append({
            "week_number": 5,
            "name": "Staging Deployment",
            "start_date": current_date.strftime("%b %d"),
            "end_date": (current_date + timedelta(days=6)).strftime("%b %d"),
            "tasks": week5_tasks,
            "total_hours": sum(t["hours"] for t in week5_tasks),
            "completion": 0,
            "focus": "Staging environment validation",
            "deliverables": ["Staging deployment", "UAT results", "Migration plan"],
            "blockers": []
        })
    
    if total_weeks >= 6:
        # Week 6: Production Launch
        current_date += timedelta(weeks=1)
        week6_tasks = [
            {"name": "Production Deployment", "status": "pending", "hours": 8},
            {"name": "Monitoring Setup", "status": "pending", "hours": 4},
            {"name": "Incident Response Plan", "status": "pending", "hours": 4},
            {"name": "Post-Launch Review", "status": "pending", "hours": 2}
        ]
        
        weeks.append({
            "week_number": 6,
            "name": "Production Launch",
            "start_date": current_date.strftime("%b %d"),
            "end_date": (current_date + timedelta(days=6)).strftime("%b %d"),
            "tasks": week6_tasks,
            "total_hours": sum(t["hours"] for t in week6_tasks),
            "completion": 0,
            "focus": "Production deployment and monitoring",
            "deliverables": ["Live production", "Monitoring dashboards", "Incident plan"],
            "blockers": []
        })
    
    return weeks


def _calculate_week_completion(tasks: List[Dict[str, Any]]) -> int:
    """Calculate completion percentage for a week"""
    if not tasks:
        return 0
    ready_tasks = sum(1 for t in tasks if t["status"] == "ready")
    return int((ready_tasks / len(tasks)) * 100)


def _identify_milestones(weeks: List[Dict[str, Any]], readiness_score: int) -> List[Dict[str, Any]]:
    """Identify key milestones in the roadmap"""
    milestones = []
    
    # Milestone 1: Infrastructure Ready
    milestones.append({
        "name": "Infrastructure Ready",
        "week": 2,
        "date": weeks[1]["end_date"] if len(weeks) > 1 else weeks[0]["end_date"],
        "description": "Core infrastructure deployed and operational",
        "criteria": ["Docker running", "K8s cluster active", "CI/CD pipeline functional"],
        "status": "pending"
    })
    
    # Milestone 2: Testing Complete (if applicable)
    if len(weeks) >= 3:
        milestones.append({
            "name": "Testing Complete",
            "week": 3,
            "date": weeks[2]["end_date"],
            "description": "All tests passing and security validated",
            "criteria": ["Integration tests pass", "Security scan clean", "Performance acceptable"],
            "status": "pending"
        })
    
    # Milestone 3: Production Ready
    final_week = len(weeks)
    milestones.append({
        "name": "Production Ready",
        "week": final_week,
        "date": weeks[-1]["end_date"],
        "description": "System ready for production deployment",
        "criteria": ["All tests pass", "Documentation complete", "Team trained"],
        "status": "pending"
    })
    
    return milestones


def _map_dependencies(weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map dependencies between tasks and weeks"""
    dependencies = []
    
    for i, week in enumerate(weeks):
        if i > 0:
            dependencies.append({
                "from_week": i,
                "to_week": i + 1,
                "type": "sequential",
                "description": f"Week {i + 1} depends on Week {i} completion"
            })
    
    # Add specific task dependencies
    dependencies.append({
        "from_task": "Docker Configuration",
        "to_task": "Kubernetes Deployment",
        "type": "prerequisite",
        "description": "K8s requires Docker containers"
    })
    
    dependencies.append({
        "from_task": "Core Infrastructure",
        "to_task": "Testing & Security",
        "type": "prerequisite",
        "description": "Testing requires deployed infrastructure"
    })
    
    return dependencies


def _assign_teams(weeks: List[Dict[str, Any]], project_type: str) -> Dict[str, List[str]]:
    """Assign team roles to different phases"""
    return {
        "DevOps Engineer": ["Week 1", "Week 2", "All weeks"],
        "Backend Developer": ["Week 1", "Week 3", "Week 4"] if "Backend" in project_type else ["Week 3"],
        "QA Engineer": ["Week 3", "Week 5"] if len(weeks) >= 5 else ["Week 3"],
        "Security Specialist": ["Week 3"],
        "Technical Writer": ["Week 4"] if len(weeks) >= 4 else []
    }


def _calculate_progress_metrics(weeks: List[Dict[str, Any]], readiness_score: int) -> Dict[str, Any]:
    """Calculate overall progress metrics"""
    total_tasks = sum(len(week["tasks"]) for week in weeks)
    completed_tasks = sum(
        sum(1 for task in week["tasks"] if task["status"] == "ready")
        for week in weeks
    )
    
    total_hours = sum(week["total_hours"] for week in weeks)
    
    return {
        "overall_completion": int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0,
        "tasks_completed": completed_tasks,
        "tasks_total": total_tasks,
        "hours_estimated": total_hours,
        "readiness_score": readiness_score,
        "on_track": readiness_score >= 60
    }


def _identify_critical_path(weeks: List[Dict[str, Any]]) -> List[str]:
    """Identify the critical path through the roadmap"""
    critical_path = []
    
    for week in weeks:
        # Find the longest task in each week
        if week["tasks"]:
            longest_task = max(week["tasks"], key=lambda t: t["hours"])
            critical_path.append(f"Week {week['week_number']}: {longest_task['name']}")
    
    return critical_path

# Made with Bob
