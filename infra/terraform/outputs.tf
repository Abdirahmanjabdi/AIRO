output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "brain_ecr_repository_url" {
  description = "ECR repository URI for the Sentinel brain image"
  value       = aws_ecr_repository.brain.repository_url
}

output "mt5_ecr_repository_url" {
  description = "ECR repository URI for the Sentinel MT5 image"
  value       = aws_ecr_repository.mt5.repository_url
}

output "model_bucket_name" {
  description = "S3 bucket used for model persistence"
  value       = aws_s3_bucket.models.bucket
}

output "redis_endpoint" {
  description = "Redis endpoint for runtime wiring"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}
