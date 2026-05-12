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

  cluster_name                   = "sentinel-${var.environment}"
  cluster_version                = "1.30"
  cluster_endpoint_public_access = true

  enable_cluster_creator_admin_permissions = true
  authentication_mode                      = "API_AND_CONFIG_MAP"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Managed Node Groups
  eks_managed_node_groups = {
    # Brain API nodes (stateless, CPU-optimized)
    brain = {
      instance_types = local.brain_instance_types
      min_size       = local.brain_min_size
      max_size       = local.brain_max_size
      desired_size   = local.brain_desired_size
      ami_type       = "AL2023_x86_64_STANDARD"
      disk_size      = 20
      capacity_type  = "ON_DEMAND"

      labels = {
        workload = "brain"
      }

      iam_role_additional_policies = {
        sentinel_model_store = aws_iam_policy.brain_model_store.arn
      }
    }

    # MT5 Pod nodes (memory-intensive, dedicated)
    mt5 = {
      instance_types = local.mt5_instance_types
      min_size       = local.mt5_min_size
      max_size       = local.mt5_max_size
      desired_size   = local.mt5_desired_size
      ami_type       = "AL2023_x86_64_STANDARD"
      disk_size      = 20
      capacity_type  = "SPOT"

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
  engine_version = local.rds_engine_version
  family         = local.rds_family
  instance_class = local.rds_instance_class

  allocated_storage     = local.rds_allocated_storage
  max_allocated_storage = local.rds_max_allocated_storage

  db_name                = "sentinel"
  username               = "sentinel"
  port                   = 5432
  create_db_subnet_group = true

  vpc_security_group_ids = [module.vpc.default_security_group_id]
  subnet_ids             = module.vpc.private_subnets

  backup_retention_period = local.rds_backup_retention_period
  skip_final_snapshot     = var.environment != "prod"
  apply_immediately       = var.environment != "prod"
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

resource "aws_vpc_security_group_ingress_rule" "postgres_from_eks_nodes" {
  security_group_id            = module.vpc.default_security_group_id
  referenced_security_group_id = module.eks.node_security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "Allow Sentinel EKS nodes to reach PostgreSQL."
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_eks_nodes" {
  security_group_id            = module.vpc.default_security_group_id
  referenced_security_group_id = module.eks.node_security_group_id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  description                  = "Allow Sentinel EKS nodes to reach Redis."
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

resource "aws_s3_bucket_lifecycle_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}

# =============================================================================
# ECR REPOSITORIES (Runtime Images)
# =============================================================================

resource "aws_ecr_repository" "brain" {
  name                 = "sentinel-brain"
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment != "prod"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_repository" "mt5" {
  name                 = "sentinel-mt5"
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment != "prod"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# =============================================================================
# IAM (Brain access to the model bucket)
# =============================================================================

resource "aws_iam_policy" "brain_model_store" {
  name        = "sentinel-${var.environment}-brain-model-store"
  description = "Allow Sentinel brain nodes to read and write personalized models."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = aws_s3_bucket.models.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.models.arn}/*"
      }
    ]
  })

  tags = local.common_tags
}

# =============================================================================
# LOCALS
# =============================================================================

locals {
  brain_instance_types = var.environment == "dev" ? ["t3.micro"] : ["c6i.xlarge"]
  brain_min_size       = var.environment == "dev" ? 2 : 2
  brain_max_size       = var.environment == "dev" ? 3 : 10
  brain_desired_size   = var.environment == "dev" ? 2 : 2

  mt5_instance_types = var.environment == "dev" ? ["t3.micro"] : ["r6i.xlarge"]
  mt5_min_size       = var.environment == "dev" ? 1 : 1
  mt5_max_size       = var.environment == "dev" ? 2 : 50
  mt5_desired_size   = var.environment == "dev" ? 1 : 2

  rds_engine_version          = var.environment == "dev" ? "11.22-rds.20250220" : "16.2"
  rds_family                  = var.environment == "dev" ? "postgres11" : "postgres16"
  rds_instance_class          = var.environment == "dev" ? "db.t3.micro" : var.rds_instance_class
  rds_allocated_storage       = var.environment == "dev" ? 20 : 50
  rds_max_allocated_storage   = var.environment == "dev" ? 20 : 500
  rds_backup_retention_period = 0 # Force 0 to bypass AWS FreeTierRestrictionError

  common_tags = {
    Project     = "sentinel-zero"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
