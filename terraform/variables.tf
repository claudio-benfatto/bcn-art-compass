# Variables for BCN Art Compass Terraform Configuration

variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "bcn-art-compass"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-southwest1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "bcn-art-compass"
}

variable "docker_image" {
  description = "Docker image for Cloud Run (will be overridden by CI/CD)"
  type        = string
  default     = "gcr.io/bcn-art-compass/bcn-art-compass:latest"
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 1
}

variable "cpu_limit" {
  description = "CPU limit for Cloud Run container"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit for Cloud Run container"
  type        = string
  default     = "512Mi"
}

variable "request_timeout" {
  description = "Request timeout in seconds"
  type        = number
  default     = 60
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access to Cloud Run service"
  type        = bool
  default     = true
}

variable "use_vertex_rag" {
  description = "Enable Vertex AI Vector Search for RAG"
  type        = bool
  default     = false
}

variable "embedding_dimensions" {
  description = "Dimensions of embedding vectors (768 for text-embedding-005)"
  type        = number
  default     = 768
}
