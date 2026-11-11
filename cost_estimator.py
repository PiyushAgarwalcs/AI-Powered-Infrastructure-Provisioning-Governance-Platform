"""
ShipSage AWS Cost Estimator - Calculate monthly infrastructure costs
Estimates costs based on generated Terraform configurations
"""
import re
from typing import Dict, List, Optional


class AWSCostEstimator:
    """Estimate AWS infrastructure costs from Terraform configs."""
    
    # AWS Pricing (US East 1, as of 2026) - approximate monthly costs
    PRICING = {
        # EKS
        "eks_cluster": 73.00,  # $0.10/hour
        "eks_node_t3_medium": 30.37,  # $0.0416/hour
        "eks_node_t3_large": 60.74,  # $0.0832/hour
        "eks_node_t3_xlarge": 121.47,  # $0.1664/hour
        
        # RDS PostgreSQL
        "rds_t3_micro": 12.41,  # $0.017/hour
        "rds_t3_small": 24.82,  # $0.034/hour
        "rds_t3_medium": 49.64,  # $0.068/hour
        "rds_storage_gb": 0.115,  # per GB/month
        "rds_backup_gb": 0.095,  # per GB/month
        
        # DocumentDB
        "docdb_t3_medium": 69.35,  # $0.095/hour
        "docdb_storage_gb": 0.10,  # per GB/month
        
        # ECR
        "ecr_storage_gb": 0.10,  # per GB/month
        
        # S3
        "s3_storage_gb": 0.023,  # Standard storage per GB/month
        "s3_requests_1k": 0.0004,  # PUT/POST per 1000 requests
        
        # Data Transfer
        "data_transfer_gb": 0.09,  # Out to internet per GB
        
        # NAT Gateway
        "nat_gateway": 32.85,  # $0.045/hour
        "nat_data_gb": 0.045,  # per GB processed
        
        # Load Balancer
        "alb": 16.43,  # $0.0225/hour
        "alb_lcu": 5.84,  # per LCU-hour
    }
    
    def __init__(self):
        self.costs = {}
        self.warnings = []
        self.optimizations = []
    
    def estimate_from_terraform(self, terraform_config: str) -> Dict:
        """
        Parse Terraform config and estimate costs.
        
        Args:
            terraform_config: Generated Terraform configuration string
        
        Returns:
            Dictionary with cost breakdown and recommendations
        """
        self.costs = {}
        self.warnings = []
        self.optimizations = []
        
        # Parse EKS cluster
        if "module \"eks\"" in terraform_config or "aws_eks_cluster" in terraform_config:
            self._estimate_eks(terraform_config)
        
        # Parse RDS
        if "aws_db_instance" in terraform_config:
            self._estimate_rds(terraform_config)
        
        # Parse DocumentDB
        if "aws_docdb_cluster" in terraform_config:
            self._estimate_documentdb(terraform_config)
        
        # Parse ECR
        if "aws_ecr_repository" in terraform_config:
            self._estimate_ecr(terraform_config)
        
        # Parse S3
        if "aws_s3_bucket" in terraform_config:
            self._estimate_s3(terraform_config)
        
        # Parse VPC/Networking
        if "enable_nat_gateway" in terraform_config:
            self._estimate_networking(terraform_config)
        
        # Calculate total
        total = sum(self.costs.values())
        
        # Generate optimizations
        self._generate_optimizations(total)
        
        return {
            "monthly_total": round(total, 2),
            "breakdown": {k: round(v, 2) for k, v in self.costs.items()},
            "warnings": self.warnings,
            "optimizations": self.optimizations,
            "currency": "USD",
            "region": "us-east-1",
            "disclaimer": "Estimates are approximate. Actual costs may vary based on usage patterns, data transfer, and AWS pricing changes."
        }
    
    def _estimate_eks(self, config: str):
        """Estimate EKS cluster costs."""
        # Base cluster cost
        self.costs["EKS Cluster"] = self.PRICING["eks_cluster"]
        
        # Parse node configuration
        node_type = "t3.medium"  # default
        if "t3.large" in config:
            node_type = "t3.large"
        elif "t3.xlarge" in config:
            node_type = "t3.xlarge"
        
        # Parse node count
        min_size = self._extract_number(config, r"min_size\s*=\s*(\d+)", 2)
        max_size = self._extract_number(config, r"max_size\s*=\s*(\d+)", 5)
        desired_size = self._extract_number(config, r"desired_size\s*=\s*(\d+)", 3)
        
        # Use desired size for estimation
        node_count = desired_size
        node_cost_key = f"eks_node_{node_type.replace('.', '_')}"
        node_cost = self.PRICING.get(node_cost_key, self.PRICING["eks_node_t3_medium"])
        
        self.costs[f"EKS Nodes ({node_count}x {node_type})"] = node_cost * node_count
        
        if node_count >= 5:
            self.warnings.append(f"Running {node_count} nodes. Consider using auto-scaling to reduce costs during low traffic.")
    
    def _estimate_rds(self, config: str):
        """Estimate RDS PostgreSQL costs."""
        # Parse instance class
        instance_class = "db.t3.micro"  # default
        if "db.t3.small" in config:
            instance_class = "db.t3.small"
        elif "db.t3.medium" in config:
            instance_class = "db.t3.medium"
        
        # Parse storage
        storage_gb = self._extract_number(config, r"allocated_storage\s*=\s*(\d+)", 20)
        
        # Calculate costs
        instance_key = instance_class.replace("db.", "rds_").replace(".", "_")
        instance_cost = self.PRICING.get(instance_key, self.PRICING["rds_t3_micro"])
        storage_cost = storage_gb * self.PRICING["rds_storage_gb"]
        backup_cost = storage_gb * 0.5 * self.PRICING["rds_backup_gb"]  # Assume 50% backup size
        
        self.costs[f"RDS Instance ({instance_class})"] = instance_cost
        self.costs[f"RDS Storage ({storage_gb}GB)"] = storage_cost
        self.costs["RDS Backups"] = backup_cost
        
        if storage_gb < 100:
            self.optimizations.append("Consider using Aurora Serverless for small databases to reduce costs.")
    
    def _estimate_documentdb(self, config: str):
        """Estimate DocumentDB costs."""
        # Base instance cost
        self.costs["DocumentDB Instance (t3.medium)"] = self.PRICING["docdb_t3_medium"]
        
        # Storage (estimate 50GB)
        storage_gb = 50
        self.costs[f"DocumentDB Storage ({storage_gb}GB)"] = storage_gb * self.PRICING["docdb_storage_gb"]
        
        self.optimizations.append("DocumentDB is expensive. Consider using MongoDB Atlas or self-hosted MongoDB on EC2 for cost savings.")
    
    def _estimate_ecr(self, config: str):
        """Estimate ECR costs."""
        # Estimate 10GB of container images
        storage_gb = 10
        self.costs[f"ECR Storage ({storage_gb}GB)"] = storage_gb * self.PRICING["ecr_storage_gb"]
        
        self.optimizations.append("Implement image lifecycle policies to automatically delete old images and reduce ECR costs.")
    
    def _estimate_s3(self, config: str):
        """Estimate S3 costs."""
        # Estimate 100GB storage and 1M requests/month
        storage_gb = 100
        requests_millions = 1
        
        self.costs[f"S3 Storage ({storage_gb}GB)"] = storage_gb * self.PRICING["s3_storage_gb"]
        self.costs[f"S3 Requests ({requests_millions}M)"] = requests_millions * 1000 * self.PRICING["s3_requests_1k"]
        
        self.optimizations.append("Use S3 Intelligent-Tiering to automatically move infrequently accessed data to cheaper storage classes.")
    
    def _estimate_networking(self, config: str):
        """Estimate VPC and networking costs."""
        # NAT Gateway
        nat_count = 1
        if "single_nat_gateway = false" in config or "single_nat_gateway=false" in config:
            nat_count = 2  # One per AZ
        
        self.costs[f"NAT Gateway ({nat_count}x)"] = self.PRICING["nat_gateway"] * nat_count
        
        # Estimate 500GB data transfer through NAT
        nat_data_gb = 500
        self.costs[f"NAT Data Processing ({nat_data_gb}GB)"] = nat_data_gb * self.PRICING["nat_data_gb"]
        
        # ALB
        self.costs["Application Load Balancer"] = self.PRICING["alb"]
        self.costs["ALB Processing (10 LCU)"] = 10 * self.PRICING["alb_lcu"]
        
        # Data transfer out
        data_out_gb = 100
        self.costs[f"Data Transfer Out ({data_out_gb}GB)"] = data_out_gb * self.PRICING["data_transfer_gb"]
        
        if nat_count > 1:
            self.optimizations.append("Using multiple NAT Gateways increases costs. Consider single NAT Gateway for dev/staging environments.")
        
        self.optimizations.append("Use CloudFront CDN to reduce data transfer costs by caching static content at edge locations.")
    
    def _extract_number(self, text: str, pattern: str, default: int) -> int:
        """Extract a number from text using regex pattern."""
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
        return default
    
    def _generate_optimizations(self, total: float):
        """Generate cost optimization recommendations based on total."""
        if total > 500:
            self.optimizations.insert(0, f"💰 High monthly cost (${total:.2f}). Consider using Spot Instances for EKS nodes to save up to 70%.")
        
        if total > 1000:
            self.optimizations.insert(0, f"⚠️ Very high monthly cost (${total:.2f}). Review resource sizing and consider Reserved Instances for 1-year commitment to save 30-40%.")
        
        # Always add these general optimizations
        self.optimizations.append("Enable AWS Cost Explorer and set up billing alerts to monitor spending.")
        self.optimizations.append("Use AWS Compute Optimizer to get rightsizing recommendations for EC2 instances.")
        self.optimizations.append("Implement auto-scaling policies to scale down resources during off-peak hours.")
    
    def estimate_simple(self, stack: List[str], has_database: bool = False) -> Dict:
        """
        Simple cost estimation based on detected stack.
        Used when Terraform config is not available.
        
        Args:
            stack: List of detected technologies
            has_database: Whether project uses a database
        
        Returns:
            Cost estimate dictionary
        """
        self.costs = {}
        self.warnings = []
        self.optimizations = []
        
        # Base EKS setup
        self.costs["EKS Cluster"] = self.PRICING["eks_cluster"]
        self.costs["EKS Nodes (3x t3.medium)"] = self.PRICING["eks_node_t3_medium"] * 3
        
        # Database if detected
        if has_database or any(db in stack for db in ["PostgreSQL", "MongoDB", "MySQL"]):
            if "MongoDB" in stack:
                self.costs["DocumentDB Instance"] = self.PRICING["docdb_t3_medium"]
                self.costs["DocumentDB Storage (50GB)"] = 50 * self.PRICING["docdb_storage_gb"]
            else:
                self.costs["RDS Instance (t3.small)"] = self.PRICING["rds_t3_small"]
                self.costs["RDS Storage (20GB)"] = 20 * self.PRICING["rds_storage_gb"]
        
        # Networking
        self.costs["NAT Gateway"] = self.PRICING["nat_gateway"]
        self.costs["Application Load Balancer"] = self.PRICING["alb"]
        
        # Storage
        self.costs["ECR Storage (10GB)"] = 10 * self.PRICING["ecr_storage_gb"]
        self.costs["S3 Storage (100GB)"] = 100 * self.PRICING["s3_storage_gb"]
        
        # Data transfer
        self.costs["Data Transfer (100GB)"] = 100 * self.PRICING["data_transfer_gb"]
        
        total = sum(self.costs.values())
        self._generate_optimizations(total)
        
        return {
            "monthly_total": round(total, 2),
            "breakdown": {k: round(v, 2) for k, v in self.costs.items()},
            "warnings": self.warnings,
            "optimizations": self.optimizations,
            "currency": "USD",
            "region": "us-east-1",
            "disclaimer": "Estimates are approximate and based on typical usage patterns. Actual costs may vary."
        }


def estimate_cost_from_analysis(analysis_data: dict) -> dict:
    """
    Estimate AWS costs from analysis data.
    
    Args:
        analysis_data: Repository analysis results
    
    Returns:
        Cost estimation dictionary
    """
    estimator = AWSCostEstimator()
    
    # If Terraform config is available, use it
    if "aws_terraform" in analysis_data:
        return estimator.estimate_from_terraform(analysis_data["aws_terraform"])
    
    # Otherwise, use simple estimation
    stack = analysis_data.get("stack", [])
    has_db = any(db in str(stack) for db in ["PostgreSQL", "MongoDB", "MySQL", "Redis"])
    
    return estimator.estimate_simple(stack, has_db)

# Made with Bob
