# Outputs for BCN Art Compass Infrastructure

output "cloud_run_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.bcn_art_compass.uri
}

output "vertex_index_id" {
  description = "ID of the Vertex AI Vector Search index"
  value       = google_vertex_ai_index.art_events.id
}

output "vertex_index_name" {
  description = "Resource name of the Vertex AI index"
  value       = google_vertex_ai_index.art_events.name
}

output "vertex_endpoint_id" {
  description = "ID of the Vertex AI index endpoint"
  value       = google_vertex_ai_index_endpoint.art_events.id
}

output "vertex_endpoint_name" {
  description = "Resource name of the Vertex AI endpoint"
  value       = google_vertex_ai_index_endpoint.art_events.name
}

output "vertex_endpoint_domain" {
  description = "Public endpoint domain for Vertex AI queries"
  value       = google_vertex_ai_index_endpoint.art_events.public_endpoint_domain_name
}

output "deployed_index_id" {
  description = "ID of the deployed index"
  value       = google_vertex_ai_index_endpoint_deployed_index.art_events.deployed_index_id
}

output "embeddings_bucket" {
  description = "GCS bucket for embeddings"
  value       = google_storage_bucket.vertex_embeddings.name
}

output "service_account_email" {
  description = "Email of the Cloud Run service account"
  value       = google_service_account.cloud_run.email
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

output "secret_name" {
  description = "Name of the Google API key secret"
  value       = google_secret_manager_secret.google_api_key.secret_id
}
