resource "kubernetes_namespace" "tenant" {
  metadata {
    name = var.tenant_name
    labels = {
      tenant      = var.tenant_name
      environment = var.environment
      managed-by  = "terraform"
    }
  }
}

resource "kubernetes_resource_quota" "tenant" {
  metadata {
    name      = "${var.tenant_name}-quota"
    namespace = kubernetes_namespace.tenant.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = var.cpu_limit == "1000m" ? "500m" : "250m"
      "requests.memory" = "512Mi"
      "limits.cpu"      = var.cpu_limit
      "limits.memory"   = var.memory_limit
      "pods"            = var.max_pods
    }
  }
}

resource "kubernetes_network_policy" "tenant_isolation" {
  metadata {
    name      = "${var.tenant_name}-isolation"
    namespace = kubernetes_namespace.tenant.metadata[0].name
  }

  spec {
    pod_selector {}

    ingress {
      from {
        namespace_selector {
          match_labels = {
            tenant = var.tenant_name
          }
        }
      }
    }

    policy_types = ["Ingress"]
  }
}