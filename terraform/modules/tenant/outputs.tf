output "namespace_name" {
  description = "Name of created namespace"
  value       = kubernetes_namespace.tenant.metadata[0].name
}