variable "aws_region" {
  description = "AWS region for the cluster"
  type        = string
  default     = "eu-west-2" # London (LD4 proximity)
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t4g.medium"
}

variable "redis_node_groups" {
  description = "Number of Redis cluster-mode shards"
  type        = number
  default     = 3
}

variable "redis_replicas_per_node_group" {
  description = "Replica count per Redis shard"
  type        = number
  default     = 1
}

variable "karpenter_chart_version" {
  description = "Karpenter Helm chart version"
  type        = string
  default     = "1.0.8"
}

variable "karpenter_mt5_cpu_limit" {
  description = "Aggregate CPU ceiling for the elastic MT5 Karpenter node pool"
  type        = number
  default     = 10000
}

variable "karpenter_mt5_memory_limit" {
  description = "Aggregate memory ceiling for the elastic MT5 Karpenter node pool"
  type        = string
  default     = "40Ti"
}

variable "aws_load_balancer_controller_chart_version" {
  description = "AWS Load Balancer Controller Helm chart version"
  type        = string
  default     = "1.8.4"
}

variable "brain_namespace" {
  description = "Kubernetes namespace that hosts the Sentinel Brain service"
  type        = string
  default     = "sentinel"
}

variable "brain_service_name" {
  description = "Kubernetes service name for the Sentinel Brain API"
  type        = string
  default     = "sentinel-brain"
}

variable "brain_hostname" {
  description = "DNS hostname for the Sentinel Brain API ingress"
  type        = string
  default     = "api.sentinel.example.com"
}

variable "brain_acm_certificate_arn" {
  description = "ACM certificate ARN for the Sentinel Brain ALB listener"
  type        = string
  default     = "arn:aws:acm:eu-west-2:000000000000:certificate/replace-me"
}
