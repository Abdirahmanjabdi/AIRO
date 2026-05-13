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
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
    }
  }

}

provider "aws" {
  region = var.aws_region
}

data "aws_eks_cluster" "this" {
  name = module.eks.cluster_name
}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
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

# TODO(10k-scale): migrate the MT5 data plane from fixed managed node groups to
# EKS Auto Mode or Karpenter once Vanguard telemetry proves pod density, MT5 RAM
# footprint, and broker-session recovery timings. The current Spot + On-Demand
# failover split is suitable for controlled beta capacity, not automatic 10k
# user burst scaling.
# TODO(10k-scale): add AWS Load Balancer Controller/Ingress for the Brain API
# and replace single-node Redis with ElastiCache replication group cluster mode
# before public multi-region launch.

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

    # MT5 failover nodes (kept near-zero; Cluster Autoscaler can expand if Spot is reclaimed)
    mt5_failover = {
      instance_types = local.mt5_failover_instance_types
      min_size       = 0
      max_size       = local.mt5_failover_max_size
      desired_size   = 0
      ami_type       = "AL2023_x86_64_STANDARD"
      disk_size      = 20
      capacity_type  = "ON_DEMAND"

      labels = {
        workload = "mt5"
        capacity = "failover"
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
# KARPENTER (Elastic MT5 Data Plane)
# =============================================================================

module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 20.0"

  cluster_name = module.eks.cluster_name

  enable_pod_identity             = true
  create_pod_identity_association = true

  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  tags = local.common_tags
}

resource "helm_release" "karpenter" {
  namespace        = "kube-system"
  create_namespace = false

  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_chart_version

  set {
    name  = "settings.clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "settings.interruptionQueue"
    value = module.karpenter.queue_name
  }

  set {
    name  = "controller.resources.requests.cpu"
    value = "1"
  }

  set {
    name  = "controller.resources.requests.memory"
    value = "1Gi"
  }

  depends_on = [module.karpenter]
}

resource "kubernetes_manifest" "karpenter_mt5_node_class" {
  manifest = {
    apiVersion = "karpenter.k8s.aws/v1"
    kind       = "EC2NodeClass"
    metadata = {
      name = "sentinel-mt5"
    }
    spec = {
      role = module.karpenter.node_iam_role_name
      subnetSelectorTerms = [
        {
          tags = {
            "Name" = "sentinel-${var.environment}-vpc-private-*"
          }
        }
      ]
      securityGroupSelectorTerms = [
        {
          id = module.eks.node_security_group_id
        }
      ]
      amiFamily = "AL2023"
      tags      = local.common_tags
    }
  }

  depends_on = [helm_release.karpenter]
}

resource "kubernetes_manifest" "karpenter_mt5_node_pool" {
  manifest = {
    apiVersion = "karpenter.sh/v1"
    kind       = "NodePool"
    metadata = {
      name = "sentinel-mt5"
    }
    spec = {
      template = {
        metadata = {
          labels = {
            workload = "mt5"
          }
        }
        spec = {
          nodeClassRef = {
            group = "karpenter.k8s.aws"
            kind  = "EC2NodeClass"
            name  = "sentinel-mt5"
          }
          taints = [
            {
              key    = "workload"
              value  = "mt5"
              effect = "NoSchedule"
            }
          ]
          requirements = [
            {
              key      = "karpenter.k8s.aws/instance-family"
              operator = "In"
              values   = ["r6i", "r6a", "m6i", "m6a"]
            },
            {
              key      = "karpenter.sh/capacity-type"
              operator = "In"
              values   = ["spot", "on-demand"]
            },
            {
              key      = "kubernetes.io/arch"
              operator = "In"
              values   = ["amd64"]
            }
          ]
        }
      }
      limits = {
        cpu    = tostring(var.karpenter_mt5_cpu_limit)
        memory = var.karpenter_mt5_memory_limit
      }
      disruption = {
        consolidationPolicy = "WhenEmptyOrUnderutilized"
        consolidateAfter    = "5m"
      }
    }
  }

  depends_on = [kubernetes_manifest.karpenter_mt5_node_class]
}

# =============================================================================
# AWS LOAD BALANCER CONTROLLER + BRAIN INGRESS
# =============================================================================

data "aws_iam_policy_document" "aws_load_balancer_controller_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.oidc_provider, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "aws_iam_role" "aws_load_balancer_controller" {
  name               = "sentinel-${var.environment}-aws-lbc"
  assume_role_policy = data.aws_iam_policy_document.aws_load_balancer_controller_assume_role.json

  tags = local.common_tags
}

resource "aws_iam_policy" "aws_load_balancer_controller" {
  name        = "sentinel-${var.environment}-aws-load-balancer-controller"
  description = "Allow AWS Load Balancer Controller to manage ALB resources for Sentinel."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "acm:DescribeCertificate",
          "acm:ListCertificates",
          "acm:GetCertificate",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:CreateSecurityGroup",
          "ec2:CreateTags",
          "ec2:DeleteSecurityGroup",
          "ec2:DeleteTags",
          "ec2:DescribeAccountAttributes",
          "ec2:DescribeAddresses",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeCoipPools",
          "ec2:DescribeInstances",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeTags",
          "ec2:DescribeVpcs",
          "ec2:ModifyNetworkInterfaceAttribute",
          "ec2:RevokeSecurityGroupIngress",
          "elasticloadbalancing:AddListenerCertificates",
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:CreateRule",
          "elasticloadbalancing:CreateTargetGroup",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:DeleteRule",
          "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:DeregisterTargets",
          "elasticloadbalancing:DescribeListenerCertificates",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeLoadBalancerAttributes",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:DescribeSSLPolicies",
          "elasticloadbalancing:DescribeTags",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetGroupAttributes",
          "elasticloadbalancing:DescribeTargetHealth",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:ModifyRule",
          "elasticloadbalancing:ModifyTargetGroup",
          "elasticloadbalancing:ModifyTargetGroupAttributes",
          "elasticloadbalancing:RegisterTargets",
          "elasticloadbalancing:RemoveListenerCertificates",
          "elasticloadbalancing:RemoveTags",
          "elasticloadbalancing:SetIpAddressType",
          "elasticloadbalancing:SetSecurityGroups",
          "elasticloadbalancing:SetSubnets",
          "elasticloadbalancing:SetWebAcl",
          "iam:CreateServiceLinkedRole",
          "waf-regional:GetWebACLForResource",
          "waf-regional:GetWebACL",
          "waf-regional:AssociateWebACL",
          "waf-regional:DisassociateWebACL",
          "wafv2:GetWebACL",
          "wafv2:GetWebACLForResource",
          "wafv2:AssociateWebACL",
          "wafv2:DisassociateWebACL"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "aws_load_balancer_controller" {
  role       = aws_iam_role.aws_load_balancer_controller.name
  policy_arn = aws_iam_policy.aws_load_balancer_controller.arn
}

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  namespace  = "kube-system"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = var.aws_load_balancer_controller_chart_version

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.aws_load_balancer_controller.arn
  }

  depends_on = [aws_iam_role_policy_attachment.aws_load_balancer_controller]
}

resource "kubernetes_ingress_v1" "sentinel_brain" {
  metadata {
    name      = "sentinel-brain"
    namespace = var.brain_namespace
    annotations = {
      "alb.ingress.kubernetes.io/certificate-arn"  = var.brain_acm_certificate_arn
      "alb.ingress.kubernetes.io/healthcheck-path" = "/readyz"
      "alb.ingress.kubernetes.io/listen-ports" = jsonencode([
        { HTTPS = 443 }
      ])
      "alb.ingress.kubernetes.io/scheme"      = "internet-facing"
      "alb.ingress.kubernetes.io/ssl-policy"  = "ELBSecurityPolicy-TLS13-1-2-2021-06"
      "alb.ingress.kubernetes.io/target-type" = "ip"
    }
  }

  spec {
    ingress_class_name = "alb"

    rule {
      host = var.brain_hostname

      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = var.brain_service_name
              port {
                number = 8000
              }
            }
          }
        }
      }
    }
  }

  depends_on = [helm_release.aws_load_balancer_controller]
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

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "sentinel-${var.environment}"
  description                = "Sentinel high-throughput runtime state store"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.redis_node_type
  port                       = 6379
  parameter_group_name       = "default.redis7.cluster.on"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [module.vpc.default_security_group_id]
  automatic_failover_enabled = true
  multi_az_enabled           = true
  num_node_groups            = var.redis_node_groups
  replicas_per_node_group    = var.redis_replicas_per_node_group
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  apply_immediately          = var.environment != "prod"

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

  mt5_instance_types          = var.environment == "dev" ? ["t3.micro"] : ["r6i.xlarge", "r6a.xlarge", "m6i.xlarge"]
  mt5_failover_instance_types = var.environment == "dev" ? ["t3.micro"] : ["r6i.xlarge", "m6i.xlarge"]
  mt5_min_size                = var.environment == "dev" ? 1 : 1
  mt5_max_size                = var.environment == "dev" ? 2 : 250
  mt5_desired_size            = var.environment == "dev" ? 1 : 2
  mt5_failover_max_size       = var.environment == "dev" ? 1 : 40

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
