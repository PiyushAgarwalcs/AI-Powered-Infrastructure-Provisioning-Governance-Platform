"""
Professional Visualizations Module
Generates data for radar charts, confidence meters, and other visual components
"""

from typing import Dict, List, Any


def generate_technology_radar(stack: List[str], readiness: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate technology maturity radar chart data.
    
    Args:
        stack: List of detected technologies
        readiness: Readiness assessment data
        
    Returns:
        Radar chart configuration with 5 dimensions
    """
    
    signals = readiness.get("signals", {})
    
    # 5 dimensions for radar chart
    dimensions = {
        "Infrastructure": _calculate_infrastructure_score(signals, stack),
        "Testing": _calculate_testing_score(signals),
        "Security": _calculate_security_score(signals),
        "Observability": _calculate_observability_score(signals),
        "Documentation": _calculate_documentation_score(signals)
    }
    
    return {
        "type": "radar",
        "labels": list(dimensions.keys()),
        "datasets": [{
            "label": "Current Maturity",
            "data": list(dimensions.values()),
            "backgroundColor": "rgba(59, 130, 246, 0.2)",
            "borderColor": "rgb(59, 130, 246)",
            "pointBackgroundColor": "rgb(59, 130, 246)",
            "pointBorderColor": "#fff",
            "pointHoverBackgroundColor": "#fff",
            "pointHoverBorderColor": "rgb(59, 130, 246)"
        }],
        "options": {
            "scales": {
                "r": {
                    "min": 0,
                    "max": 100,
                    "ticks": {
                        "stepSize": 20
                    }
                }
            }
        },
        "insights": _generate_radar_insights(dimensions)
    }


def generate_confidence_meter(readiness_score: int) -> Dict[str, Any]:
    """
    Generate deployment confidence meter data.
    
    Args:
        readiness_score: Overall readiness score (0-100)
        
    Returns:
        Confidence meter configuration
    """
    
    # Calculate confidence level
    if readiness_score >= 80:
        confidence = "high"
        percentage = 90
        color = "#10b981"  # green
        message = "High confidence - Ready for production deployment"
        icon = "🎯"
    elif readiness_score >= 60:
        confidence = "medium"
        percentage = 70
        color = "#3b82f6"  # blue
        message = "Medium confidence - Minor improvements recommended"
        icon = "📊"
    elif readiness_score >= 40:
        confidence = "low"
        percentage = 50
        color = "#f59e0b"  # orange
        message = "Low confidence - Significant work needed before production"
        icon = "⚠️"
    else:
        confidence = "very-low"
        percentage = 30
        color = "#ef4444"  # red
        message = "Very low confidence - Not ready for production"
        icon = "🚨"
    
    return {
        "confidence_level": confidence,
        "percentage": percentage,
        "color": color,
        "message": message,
        "icon": icon,
        "readiness_score": readiness_score,
        "gauge_config": {
            "type": "doughnut",
            "data": {
                "datasets": [{
                    "data": [percentage, 100 - percentage],
                    "backgroundColor": [color, "#e5e7eb"],
                    "borderWidth": 0
                }]
            },
            "options": {
                "cutout": "75%",
                "rotation": -90,
                "circumference": 180
            }
        }
    }


def generate_deployment_timeline_chart(roadmap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Gantt-style timeline chart data.
    
    Args:
        roadmap: Deployment roadmap data
        
    Returns:
        Timeline chart configuration
    """
    
    weeks = roadmap.get("weeks", [])
    
    # Prepare data for horizontal bar chart (Gantt-style)
    labels = [f"Week {w['week_number']}: {w['name']}" for w in weeks]
    data = [w["total_hours"] for w in weeks]
    colors = [
        "#3b82f6",  # blue
        "#8b5cf6",  # purple
        "#10b981",  # green
        "#f59e0b",  # orange
        "#ef4444",  # red
        "#06b6d4"   # cyan
    ]
    
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Hours Required",
                "data": data,
                "backgroundColor": colors[:len(data)],
                "borderRadius": 6
            }]
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "plugins": {
                "legend": {
                    "display": False
                },
                "tooltip": {
                    "callbacks": {
                        "label": "function(context) { return context.parsed.x + ' hours'; }"
                    }
                }
            },
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "title": {
                        "display": True,
                        "text": "Hours"
                    }
                }
            }
        }
    }


def generate_cost_breakdown_chart(cost_estimate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate cost breakdown pie chart.
    
    Args:
        cost_estimate: Cost estimation data
        
    Returns:
        Pie chart configuration
    """
    
    breakdown = cost_estimate.get("breakdown", {})
    
    # Group small costs into "Other"
    threshold = cost_estimate.get("monthly_total", 0) * 0.05  # 5% threshold
    main_costs = {}
    other_cost = 0
    
    for service, cost in breakdown.items():
        if cost >= threshold:
            main_costs[service] = cost
        else:
            other_cost += cost
    
    if other_cost > 0:
        main_costs["Other"] = other_cost
    
    labels = list(main_costs.keys())
    data = list(main_costs.values())
    
    # Color palette
    colors = [
        "#3b82f6", "#8b5cf6", "#10b981", "#f59e0b",
        "#ef4444", "#06b6d4", "#ec4899", "#f97316"
    ]
    
    return {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": data,
                "backgroundColor": colors[:len(data)],
                "borderWidth": 2,
                "borderColor": "#111827"
            }]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {
                    "position": "right"
                },
                "tooltip": {
                    "callbacks": {
                        "label": "function(context) { return context.label + ': $' + context.parsed.toFixed(2); }"
                    }
                }
            }
        }
    }


def generate_savings_potential_chart(cost_optimizations: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate cost savings potential bar chart.
    
    Args:
        cost_optimizations: Cost optimization recommendations
        
    Returns:
        Bar chart configuration
    """
    
    optimizations = cost_optimizations.get("optimizations", [])
    
    # Sort by savings (top 6)
    top_optimizations = sorted(
        optimizations,
        key=lambda x: x.get("potential_savings", 0),
        reverse=True
    )[:6]
    
    labels = [opt["title"] for opt in top_optimizations]
    data = [opt["potential_savings"] for opt in top_optimizations]
    percentages = [opt["savings_percentage"] for opt in top_optimizations]
    
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Potential Monthly Savings ($)",
                "data": data,
                "backgroundColor": "#10b981",
                "borderRadius": 6
            }]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {
                    "display": False
                },
                "tooltip": {
                    "callbacks": {
                        "label": "function(context) { return '$' + context.parsed.y.toFixed(2) + ' (' + percentages[context.dataIndex] + '% savings)'; }",
                        "afterLabel": "function(context) { return 'Effort: ' + top_optimizations[context.dataIndex].effort; }"
                    }
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {
                        "display": True,
                        "text": "Monthly Savings ($)"
                    }
                }
            }
        },
        "percentages": percentages
    }


def generate_progress_indicators(readiness: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate progress indicators for various metrics.
    
    Args:
        readiness: Readiness assessment data
        
    Returns:
        Progress indicator configurations
    """
    
    signals = readiness.get("signals", {})
    score = readiness.get("score", 0)
    
    indicators = {
        "overall_readiness": {
            "label": "Overall Readiness",
            "value": score,
            "max": 100,
            "color": _get_color_for_score(score),
            "icon": "📊"
        },
        "infrastructure": {
            "label": "Infrastructure",
            "value": _calculate_infrastructure_score(signals, []),
            "max": 100,
            "color": _get_color_for_score(_calculate_infrastructure_score(signals, [])),
            "icon": "🏗️"
        },
        "testing": {
            "label": "Testing Coverage",
            "value": _calculate_testing_score(signals),
            "max": 100,
            "color": _get_color_for_score(_calculate_testing_score(signals)),
            "icon": "🧪"
        },
        "security": {
            "label": "Security Posture",
            "value": _calculate_security_score(signals),
            "max": 100,
            "color": _get_color_for_score(_calculate_security_score(signals)),
            "icon": "🔒"
        },
        "documentation": {
            "label": "Documentation",
            "value": _calculate_documentation_score(signals),
            "max": 100,
            "color": _get_color_for_score(_calculate_documentation_score(signals)),
            "icon": "📚"
        }
    }
    
    return indicators


# Helper functions

def _calculate_infrastructure_score(signals: Dict[str, bool], stack: List[str]) -> int:
    """Calculate infrastructure maturity score"""
    score = 0
    if signals.get("docker"): score += 30
    if signals.get("infra"): score += 30
    if signals.get("ci"): score += 25
    if signals.get("env_template"): score += 15
    return min(score, 100)


def _calculate_testing_score(signals: Dict[str, bool]) -> int:
    """Calculate testing maturity score"""
    score = 0
    if signals.get("tests"): score += 70
    if signals.get("ci"): score += 30  # CI implies some testing
    return min(score, 100)


def _calculate_security_score(signals: Dict[str, bool]) -> int:
    """Calculate security maturity score"""
    score = 0
    if signals.get("security"): score += 50
    if signals.get("env_template"): score += 20  # Secrets management
    if signals.get("health"): score += 15  # Health checks
    if signals.get("monitoring"): score += 15  # Observability
    return min(score, 100)


def _calculate_observability_score(signals: Dict[str, bool]) -> int:
    """Calculate observability maturity score"""
    score = 0
    if signals.get("monitoring"): score += 50
    if signals.get("health"): score += 30
    if signals.get("ci"): score += 20  # CI implies some logging
    return min(score, 100)


def _calculate_documentation_score(signals: Dict[str, bool]) -> int:
    """Calculate documentation maturity score"""
    score = 0
    if signals.get("docs"): score += 70
    if signals.get("env_template"): score += 30  # Config documentation
    return min(score, 100)


def _get_color_for_score(score: int) -> str:
    """Get color based on score"""
    if score >= 80: return "#10b981"  # green
    elif score >= 60: return "#3b82f6"  # blue
    elif score >= 40: return "#f59e0b"  # orange
    else: return "#ef4444"  # red


def _generate_radar_insights(dimensions: Dict[str, int]) -> List[str]:
    """Generate insights from radar chart dimensions"""
    insights = []
    
    # Find strongest and weakest dimensions
    sorted_dims = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
    strongest = sorted_dims[0]
    weakest = sorted_dims[-1]
    
    if strongest[1] >= 80:
        insights.append(f"✅ Strong {strongest[0]} capabilities ({strongest[1]}%)")
    
    if weakest[1] < 50:
        insights.append(f"⚠️ {weakest[0]} needs improvement ({weakest[1]}%)")
    
    # Check for balanced profile
    scores = list(dimensions.values())
    if max(scores) - min(scores) < 30:
        insights.append("📊 Well-balanced technology profile")
    else:
        insights.append("📊 Uneven maturity across dimensions")
    
    return insights

# Made with Bob
