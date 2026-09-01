output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks_cluster.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks_cluster.cluster_endpoint
}

output "cluster_certificate" {
  description = "EKS cluster certificate authority"
  value       = module.eks_cluster.cluster_certificate
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.eks_cluster.vpc_id
}