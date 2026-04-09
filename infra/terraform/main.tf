# =============================================================================
# Sentinel-Zero Terraform — EKS Infrastructure
# Ref: ARCHITECTURE.md §4
#
# Usage:
#   cd infra/terraform
#   terraform init
#   terraform plan -var-file="prod.tfvars"
#   terraform apply -var-file="prod.tfvars"
# =============================================================================

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  backend "s3" {
    bucket = "sentinel-terraform-state"
    key    = "sentinel-zero/terraform.tfstate"
    region = "eu-west-2"
  }
}

provider "aws" {
  region = var.aws_region
}

# =============================================================================
# VPC
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.5"

  name = "sentinel-${var.environment}-vpc"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway = true
  single_nat_gateway = var.environment == "dev"

  tags = local.common_tags
}

# =============================================================================
# EKS CLUSTER
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "sentinel-${var.environment}"
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Managed Node Groups
  eks_managed_node_groups = {
    # Brain API nodes (stateless, CPU-optimized)
    brain = {
      instance_types = ["c6i.xlarge"]
      min_size       = 2
      max_size       = 10
      desired_size   = 2

      labels = {
        workload = "brain"
      }
    }

    # MT5 Pod nodes (memory-intensive, dedicated)
    mt5 = {
      instance_types = ["r6i.xlarge"]
      min_size       = 1
      max_size       = 50
      desired_size   = 2

      labels = {
        workload = "mt5"
      }

      taints = [{
        key    = "workload"
        value  = "mt5"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = local.common_tags
}

# =============================================================================
# RDS POSTGRESQL (Audit Trail + Metadata)
# =============================================================================

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "sentinel-${var.environment}"

  engine         = "postgres"
  engine_version = "16.2"
  instance_class = var.rds_instance_class

  allocated_storage     = 50
  max_allocated_storage = 500

  db_name  = "sentinel"
  username = "sentinel"
  port     = 5432

  vpc_security_group_ids = [module.vpc.default_security_group_id]
  subnet_ids             = module.vpc.private_subnets

  backup_retention_period = 7
  deletion_protection     = var.environment == "prod"

  tags = local.common_tags
}

# =============================================================================
# ELASTICACHE REDIS (Session Cache + Heartbeat)
# =============================================================================

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "sentinel-${var.environment}"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [module.vpc.default_security_group_id]

  tags = local.common_tags
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "sentinel-${var.environment}-redis"
  subnet_ids = module.vpc.private_subnets
}

# =============================================================================
# S3 BUCKET (Model Store — FP adjustment #3)
# =============================================================================

resource "aws_s3_bucket" "models" {
  bucket = "sentinel-models-${var.environment}-${var.aws_region}"

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# =============================================================================
# LOCALS
# =============================================================================

locals {
  common_tags = {
    Project     = "sentinel-zero"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
