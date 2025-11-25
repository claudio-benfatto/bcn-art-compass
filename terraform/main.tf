# BCN Art Compass - Main Terraform Configuration
# Manages Cloud Run, Vertex AI, and supporting infrastructure

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Optional: Use GCS backend for state management
  # Uncomment and configure after initial setup
  # backend "gcs" {
  #   bucket = "bcn-art-compass-terraform-state"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# GCS bucket for Vertex AI embeddings
resource "google_storage_bucket" "vertex_embeddings" {
  name          = "${var.project_id}-vertex-embeddings"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required_apis]
}

# Upload embeddings to GCS (if file exists locally)
# Note: This requires embeddings to be generated first
# Use scripts/update-embeddings.sh for updates without Terraform
resource "google_storage_bucket_object" "embeddings" {
  count = fileexists("${path.module}/../generated/vertex_embeddings.jsonl") ? 1 : 0

  name   = "embeddings/vertex_embeddings.json"
  bucket = google_storage_bucket.vertex_embeddings.name
  source = "${path.module}/../generated/vertex_embeddings.jsonl"

  depends_on = [google_storage_bucket.vertex_embeddings]

  # Ignore changes made outside Terraform (e.g., via update-embeddings.sh)
  lifecycle {
    ignore_changes = [
      source,
      detect_md5hash,
    ]
  }
}

# Vertex AI Vector Search Index
resource "google_vertex_ai_index" "art_events" {
  display_name = "bcn-art-compass-index"
  description  = "Vector search index for Barcelona cultural events"
  region       = var.region

  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.vertex_embeddings.name}/embeddings"
    config {
      dimensions                  = var.embedding_dimensions
      approximate_neighbors_count = 150
      distance_measure_type       = "DOT_PRODUCT_DISTANCE"

      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }

  index_update_method = "BATCH_UPDATE"

  depends_on = [
    google_project_service.required_apis,
    google_storage_bucket_object.embeddings,
  ]

  # Prevent destruction of index with data
  lifecycle {
    prevent_destroy = false # Set to true in production
  }
}

# Vertex AI Index Endpoint
resource "google_vertex_ai_index_endpoint" "art_events" {
  display_name = "bcn-art-compass-endpoint"
  description  = "Endpoint for querying art events vector index"
  region       = var.region

  public_endpoint_enabled = true

  depends_on = [google_project_service.required_apis]
}

# Deploy Index to Endpoint
resource "google_vertex_ai_index_endpoint_deployed_index" "art_events" {
  index_endpoint      = google_vertex_ai_index_endpoint.art_events.id
  index               = google_vertex_ai_index.art_events.id
  deployed_index_id   = "bcn_art_compass_deployed"
  display_name        = "BCN Art Compass Deployed Index"
  enable_access_logging = false

  # Use automatic resources for simpler configuration
  automatic_resources {
    min_replica_count = 1
    max_replica_count = 1
  }

  # Allow time for deployment
  timeouts {
    create = "60m"
    update = "60m"
    delete = "30m"
  }
}

# Secret Manager for API keys
resource "google_secret_manager_secret" "google_api_key" {
  secret_id = "google-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

# Note: Secret value must be set manually or via separate process
# You can set it with: echo -n 'YOUR_KEY' | gcloud secrets versions add google-api-key --data-file=-

# Artifact Registry for Docker images (alternative to GCR)
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "bcn-art-compass"
  description   = "Docker images for BCN Art Compass"
  format        = "DOCKER"

  depends_on = [google_project_service.required_apis]
}

# Service account for Cloud Run
resource "google_service_account" "cloud_run" {
  account_id   = "bcn-art-compass-run"
  display_name = "BCN Art Compass Cloud Run Service Account"
  description  = "Service account for Cloud Run service"
}

# Grant service account access to Secret Manager
resource "google_secret_manager_secret_iam_member" "cloud_run_secret_accessor" {
  secret_id = google_secret_manager_secret.google_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Grant service account access to Vertex AI
resource "google_project_iam_member" "cloud_run_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Grant service account access to GCS
resource "google_project_iam_member" "cloud_run_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Grant service account access to Firestore
resource "google_project_iam_member" "cloud_run_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "bcn_art_compass" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.docker_image

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true # Enable CPU throttling
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }

      env {
        name  = "USE_FIRESTORE"
        value = "true"
      }

      env {
        name  = "USE_VERTEX_RAG"
        value = var.use_vertex_rag ? "true" : "false"
      }

      env {
        name  = "USE_LOCAL_LLM"
        value = "false"
      }

      env {
        name  = "VERTEX_INDEX_ENDPOINT"
        value = var.use_vertex_rag ? google_vertex_ai_index_endpoint.art_events.id : ""
      }

      env {
        name  = "VERTEX_DEPLOYED_INDEX_ID"
        value = var.use_vertex_rag ? google_vertex_ai_index_endpoint_deployed_index.art_events.deployed_index_id : ""
      }

      # Secret reference
      env {
        name = "GOOGLE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.google_api_key.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/healthz"
        }
        initial_delay_seconds = 30
        timeout_seconds       = 3
        period_seconds        = 30
        failure_threshold     = 3
      }
    }

    timeout = "${var.request_timeout}s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run,
    google_secret_manager_secret_iam_member.cloud_run_secret_accessor,
    google_project_iam_member.cloud_run_vertex_user,
  ]

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image, # Allow external image updates via CI/CD
    ]
  }
}

# Allow unauthenticated access
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count = var.allow_unauthenticated ? 1 : 0

  location = google_cloud_run_v2_service.bcn_art_compass.location
  name     = google_cloud_run_v2_service.bcn_art_compass.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
