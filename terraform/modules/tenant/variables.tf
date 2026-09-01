variable "tenant_name" {
  description = "Name of the tenant"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "cpu_limit" {
  description = "Total CPU limit for tenant namespace"
  type        = string
  default     = "1000m"
}

variable "memory_limit" {
  description = "Total memory limit for tenant namespace"
  type        = string
  default     = "1Gi"
}

variable "max_pods" {
  description = "Maximum pods per tenant"
  type        = number
  default     = 10
}