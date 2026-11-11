"""
Enhanced Cost Optimization Recommendations
Provides detailed, actionable cost optimization strategies with savings calculations
"""

from typing import Dict, List, Any


def generate_enhanced_optimizations(
    cost_estimate: Dict[str, Any],
    readiness_score: int,
    stack: List[str]
) -> Dict[str, Any]:
    """
    Generate enhanced cost optimization recommendations with specific savings.
    
    Args:
        cost_estimate: Cost estimation data
        readiness_score: Current readiness score
        stack: Technology stack
        
    Returns:
        Dictionary with detailed optimization recommendations
    """
    
    monthly_total = cost_estimate.get("monthly_total", 0)
    breakdown = cost_estimate.get("breakdown", {})
    
    optimizations = []
    total_potential_savings = 0
    
    # 1. Spot Instances for EKS Nodes
    eks_node_cost = sum(v for k, v in breakdown.items() if "EKS Nodes" in k)
    if eks_node_cost > 0:
        spot_savings = eks_node_cost * 0.70  # 70% savings
        total_potential_savings += spot_savings
        optimizations.append({
            "title": "Use Spot Instances for EKS Worker Nodes",
            "category": "Compute",
            "priority": "high",
            "current_cost": round(eks_node_cost, 2),
            "potential_savings": round(spot_savings, 2),
            "savings_percentage": 70,
            "effort": "medium",
            "implementation_time": "2-4 hours",
            "description": "Replace On-Demand EC2 instances with Spot Instances for non-critical workloads",
            "steps": [
                "Configure EKS node groups with mixed instance types",
                "Set up Spot Instance interruption handling",
                "Use Cluster Autoscaler with Spot Instance support",
                "Implement graceful pod termination"
            ],
            "risks": [
                "Spot instances can be interrupted with 2-minute notice",
                "Not suitable for stateful or critical workloads"
            ],
            "best_practices": [
                "Use Spot for 70-80% of capacity, On-Demand for baseline",
                "Diversify instance types to reduce interruption risk",
                "Implement proper pod disruption budgets"
            ]
        })
    
    # 2. Reserved Instances for Predictable Workloads
    if monthly_total > 300:
        reserved_savings = monthly_total * 0.35  # 35% savings with 1-year RI
        total_potential_savings += reserved_savings
        optimizations.append({
            "title": "Purchase Reserved Instances (1-Year Commitment)",
            "category": "Compute",
            "priority": "high" if monthly_total > 500 else "medium",
            "current_cost": round(monthly_total, 2),
            "potential_savings": round(reserved_savings, 2),
            "savings_percentage": 35,
            "effort": "low",
            "implementation_time": "30 minutes",
            "description": "Commit to 1-year Reserved Instances for predictable baseline capacity",
            "steps": [
                "Analyze usage patterns over past 30 days",
                "Purchase RIs for baseline capacity (50-70% of peak)",
                "Use Savings Plans for flexibility across instance types",
                "Set up RI utilization monitoring"
            ],
            "risks": [
                "Requires upfront commitment",
                "Less flexibility if requirements change"
            ],
            "best_practices": [
                "Start with 1-year commitment, not 3-year",
                "Use Convertible RIs for more flexibility",
                "Monitor RI utilization monthly"
            ]
        })
    
    # 3. Auto-Scaling Optimization
    auto_scaling_savings = monthly_total * 0.25  # 25% savings
    total_potential_savings += auto_scaling_savings
    optimizations.append({
        "title": "Implement Intelligent Auto-Scaling",
        "category": "Compute",
        "priority": "high",
        "current_cost": round(monthly_total, 2),
        "potential_savings": round(auto_scaling_savings, 2),
        "savings_percentage": 25,
        "effort": "medium",
        "implementation_time": "4-6 hours",
        "description": "Scale down resources during off-peak hours and weekends",
        "steps": [
            "Set up Horizontal Pod Autoscaler (HPA) based on CPU/memory",
            "Configure Cluster Autoscaler for node scaling",
            "Implement scheduled scaling for predictable patterns",
            "Use KEDA for event-driven autoscaling"
        ],
        "risks": [
            "Aggressive scaling may impact performance",
            "Cold start times during scale-up"
        ],
        "best_practices": [
            "Set conservative scale-down delays (10-15 minutes)",
            "Use pod disruption budgets to prevent service disruption",
            "Monitor scaling metrics and adjust thresholds"
        ]
    })
    
    # 4. NAT Gateway Optimization
    nat_cost = sum(v for k, v in breakdown.items() if "NAT" in k)
    if nat_cost > 50:
        nat_savings = nat_cost * 0.50  # 50% savings
        total_potential_savings += nat_savings
        optimizations.append({
            "title": "Optimize NAT Gateway Usage",
            "category": "Networking",
            "priority": "medium",
            "current_cost": round(nat_cost, 2),
            "potential_savings": round(nat_savings, 2),
            "savings_percentage": 50,
            "effort": "medium",
            "implementation_time": "3-4 hours",
            "description": "Reduce NAT Gateway costs through VPC endpoints and single NAT",
            "steps": [
                "Use VPC endpoints for AWS services (S3, DynamoDB, ECR)",
                "Consolidate to single NAT Gateway for dev/staging",
                "Route internal traffic through private subnets",
                "Use NAT instances for very low traffic environments"
            ],
            "risks": [
                "Single NAT Gateway is single point of failure",
                "VPC endpoints have per-GB charges"
            ],
            "best_practices": [
                "Keep multi-NAT for production, single for non-prod",
                "Monitor NAT Gateway data processing charges",
                "Use S3 Gateway endpoint (free) instead of Interface endpoint"
            ]
        })
    
    # 5. Database Optimization
    db_cost = sum(v for k, v in breakdown.items() if "RDS" in k or "DocumentDB" in k)
    if db_cost > 50:
        db_savings = db_cost * 0.40  # 40% savings
        total_potential_savings += db_savings
        optimizations.append({
            "title": "Optimize Database Costs",
            "category": "Database",
            "priority": "high" if db_cost > 100 else "medium",
            "current_cost": round(db_cost, 2),
            "potential_savings": round(db_savings, 2),
            "savings_percentage": 40,
            "effort": "medium",
            "implementation_time": "4-8 hours",
            "description": "Right-size database instances and use Aurora Serverless",
            "steps": [
                "Analyze database performance metrics",
                "Consider Aurora Serverless v2 for variable workloads",
                "Use read replicas only when needed",
                "Enable automated backups with shorter retention",
                "Use gp3 storage instead of gp2 for 20% savings"
            ],
            "risks": [
                "Aurora Serverless has cold start latency",
                "Smaller instances may impact performance"
            ],
            "best_practices": [
                "Start with Aurora Serverless for dev/staging",
                "Monitor database CPU and memory utilization",
                "Use Performance Insights to identify optimization opportunities"
            ]
        })
    
    # 6. S3 Storage Optimization
    s3_cost = sum(v for k, v in breakdown.items() if "S3" in k)
    if s3_cost > 10:
        s3_savings = s3_cost * 0.60  # 60% savings
        total_potential_savings += s3_savings
        optimizations.append({
            "title": "Implement S3 Lifecycle Policies",
            "category": "Storage",
            "priority": "medium",
            "current_cost": round(s3_cost, 2),
            "potential_savings": round(s3_savings, 2),
            "savings_percentage": 60,
            "effort": "low",
            "implementation_time": "1-2 hours",
            "description": "Automatically transition objects to cheaper storage classes",
            "steps": [
                "Enable S3 Intelligent-Tiering for automatic optimization",
                "Move infrequent access data to S3-IA after 30 days",
                "Archive old data to Glacier after 90 days",
                "Delete temporary files after 7 days",
                "Enable S3 Storage Lens for visibility"
            ],
            "risks": [
                "Retrieval fees for archived data",
                "Minimum storage duration charges"
            ],
            "best_practices": [
                "Use Intelligent-Tiering for unknown access patterns",
                "Set up lifecycle rules per bucket/prefix",
                "Monitor access patterns before archiving"
            ]
        })
    
    # 7. CloudFront CDN
    data_transfer_cost = sum(v for k, v in breakdown.items() if "Data Transfer" in k)
    if data_transfer_cost > 20:
        cdn_savings = data_transfer_cost * 0.70  # 70% savings
        total_potential_savings += cdn_savings
        optimizations.append({
            "title": "Add CloudFront CDN",
            "category": "Networking",
            "priority": "high",
            "current_cost": round(data_transfer_cost, 2),
            "potential_savings": round(cdn_savings, 2),
            "savings_percentage": 70,
            "effort": "medium",
            "implementation_time": "3-4 hours",
            "description": "Cache static content at edge locations to reduce data transfer costs",
            "steps": [
                "Create CloudFront distribution",
                "Configure origin to point to ALB or S3",
                "Set appropriate cache TTLs",
                "Enable compression",
                "Use CloudFront Functions for edge logic"
            ],
            "risks": [
                "Cache invalidation complexity",
                "Initial setup requires DNS changes"
            ],
            "best_practices": [
                "Cache static assets for 1 year",
                "Use versioned URLs for cache busting",
                "Enable HTTP/2 and HTTP/3"
            ]
        })
    
    # 8. Container Image Optimization
    ecr_cost = sum(v for k, v in breakdown.items() if "ECR" in k)
    if ecr_cost > 5:
        ecr_savings = ecr_cost * 0.50  # 50% savings
        total_potential_savings += ecr_savings
        optimizations.append({
            "title": "Optimize Container Images",
            "category": "Storage",
            "priority": "low",
            "current_cost": round(ecr_cost, 2),
            "potential_savings": round(ecr_savings, 2),
            "savings_percentage": 50,
            "effort": "low",
            "implementation_time": "2-3 hours",
            "description": "Reduce image sizes and implement lifecycle policies",
            "steps": [
                "Use multi-stage Docker builds",
                "Use Alpine or distroless base images",
                "Set up ECR lifecycle policies to delete old images",
                "Keep only last 10 images per repository",
                "Scan and remove unused layers"
            ],
            "risks": [
                "Smaller images may lack debugging tools",
                "Aggressive cleanup may delete needed images"
            ],
            "best_practices": [
                "Tag images with semantic versioning",
                "Keep production images indefinitely",
                "Delete untagged images after 7 days"
            ]
        })
    
    # Sort by potential savings (highest first)
    optimizations.sort(key=lambda x: x["potential_savings"], reverse=True)
    
    # Calculate implementation roadmap
    quick_wins = [opt for opt in optimizations if opt["effort"] == "low"]
    medium_effort = [opt for opt in optimizations if opt["effort"] == "medium"]
    high_effort = [opt for opt in optimizations if opt["effort"] == "high"]
    
    return {
        "total_potential_savings": round(total_potential_savings, 2),
        "savings_percentage": round((total_potential_savings / monthly_total * 100), 1) if monthly_total > 0 else 0,
        "optimizations": optimizations,
        "quick_wins": quick_wins,
        "implementation_roadmap": {
            "phase_1_quick_wins": {
                "duration": "1-2 weeks",
                "optimizations": [opt["title"] for opt in quick_wins],
                "total_savings": round(sum(opt["potential_savings"] for opt in quick_wins), 2)
            },
            "phase_2_medium_effort": {
                "duration": "2-4 weeks",
                "optimizations": [opt["title"] for opt in medium_effort],
                "total_savings": round(sum(opt["potential_savings"] for opt in medium_effort), 2)
            },
            "phase_3_high_effort": {
                "duration": "4-8 weeks",
                "optimizations": [opt["title"] for opt in high_effort],
                "total_savings": round(sum(opt["potential_savings"] for opt in high_effort), 2)
            }
        },
        "priority_recommendations": [
            opt for opt in optimizations if opt["priority"] == "high"
        ][:3]  # Top 3 high priority
    }

# Made with Bob
