# BCN Art Compass - Terraform Infrastructure

This directory contains Terraform configurations to manage the entire BCN Art Compass infrastructure on Google Cloud Platform.

## What's Managed

### Cloud Run
- Service deployment with auto-scaling
- Service account with appropriate IAM roles
- Environment variables and secrets
- Health checks and probes

### Vertex AI
- Vector Search index for event embeddings
- Index endpoint for queries
- Deployed index configuration
- GCS bucket for embeddings storage

### Supporting Infrastructure
- Secret Manager for API keys
- Artifact Registry for Docker images
- IAM roles and permissions
- API enablement

## Prerequisites

1. **Install Terraform** (>= 1.5)
   ```bash
   brew install terraform
   ```

2. **Authenticate with GCP**
   ```bash
   gcloud auth application-default login
   gcloud config set project bcn-art-compass
   ```

3. **Generate embeddings** (required for Vertex AI)
   ```bash
   cd ..
   uv run python scripts/vertex/precompute_embeddings.py
   # This creates generated/vertex_embeddings.jsonl
   ```

4. **Set up Secret Manager secret**
   ```bash
   echo -n 'YOUR_GOOGLE_API_KEY' | gcloud secrets create google-api-key \
     --data-file=- \
     --project=bcn-art-compass
   ```

## Quick Start

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

### 2. Review the Plan

```bash
terraform plan
```

This shows what resources will be created without making any changes.

### 3. Apply Configuration

```bash
terraform apply
```

Review the changes and type `yes` to confirm.

### 4. Get Outputs

```bash
terraform output
```

This shows important information like:
- Cloud Run URL
- Vertex AI endpoint details
- Service account email

## Configuration

### Using terraform.tfvars

Copy the example file and customize:

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

Example `terraform.tfvars`:

```hcl
project_id = "bcn-art-compass"
region     = "europe-southwest1"

# Start without Vertex AI
use_vertex_rag = false
min_instances  = 0
max_instances  = 1

# Enable Vertex AI later
# use_vertex_rag = true
```

### Using Command-Line Variables

```bash
terraform apply \
  -var="project_id=bcn-art-compass" \
  -var="use_vertex_rag=true" \
  -var="max_instances=2"
```

## Deployment Workflow

### Initial Deployment (Without Vertex AI)

```bash
# 1. Initialize
terraform init

# 2. Deploy basic infrastructure
terraform apply -var="use_vertex_rag=false"

# 3. Get Cloud Run URL
terraform output cloud_run_url
```

### Enable Vertex AI Later

```bash
# 1. Ensure embeddings are generated
uv run python scripts/vertex/precompute_embeddings.py

# 2. Update configuration
terraform apply -var="use_vertex_rag=true"

# 3. Get Vertex AI details
terraform output vertex_endpoint_domain
terraform output deployed_index_id
```

### Updating Docker Image

The Docker image is managed by Cloud Build/CI/CD, not Terraform. To update:

```bash
# Option 1: Use Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Option 2: Manual deployment (Terraform will ignore this change)
gcloud run deploy bcn-art-compass \
  --image gcr.io/bcn-art-compass/bcn-art-compass:new-tag \
  --region europe-southwest1
```

## Important Resources

### Vertex AI Vector Search

- **Index**: Stores event embeddings (768 dimensions)
- **Endpoint**: Provides query interface
- **Deployed Index**: Connects index to endpoint
- **Cost**: ~$0.50/hour for n1-standard-2 machine

⚠️ **Note**: Vertex AI resources are expensive. Start with `use_vertex_rag=false` and use local ChromaDB for development.

### Cloud Run

- **Auto-scaling**: 0-1 instances by default
- **Memory**: 512Mi (sufficient for MVP)
- **CPU**: 1 core with throttling when idle
- **Cost**: Only pay for request time

## Managing State

### Local State (Default)

By default, Terraform stores state locally in `terraform.tfstate`. This file is critical and should be backed up.

### Remote State (Recommended for Production)

Uncomment the backend configuration in `main.tf`:

```hcl
terraform {
  backend "gcs" {
    bucket = "bcn-art-compass-terraform-state"
    prefix = "terraform/state"
  }
}
```

Then create the bucket and migrate:

```bash
# Create state bucket
gsutil mb -p bcn-art-compass -l europe-southwest1 gs://bcn-art-compass-terraform-state

# Enable versioning
gsutil versioning set on gs://bcn-art-compass-terraform-state

# Migrate state
terraform init -migrate-state
```

## Common Commands

```bash
# See current state
terraform show

# List resources
terraform state list

# Get specific output
terraform output cloud_run_url

# Import existing resource
terraform import google_cloud_run_v2_service.bcn_art_compass \
  projects/bcn-art-compass/locations/europe-southwest1/services/bcn-art-compass

# Destroy all resources (careful!)
terraform destroy

# Destroy specific resource
terraform destroy -target=google_vertex_ai_index.art_events

# Format code
terraform fmt

# Validate configuration
terraform validate
```

## Importing Existing Resources

If you already have resources created manually:

```bash
# Import Cloud Run service
terraform import google_cloud_run_v2_service.bcn_art_compass \
  projects/bcn-art-compass/locations/europe-southwest1/services/bcn-art-compass

# Import Secret Manager secret
terraform import google_secret_manager_secret.google_api_key \
  projects/bcn-art-compass/secrets/google-api-key

# Import GCS bucket
terraform import google_storage_bucket.vertex_embeddings \
  bcn-art-compass-vertex-embeddings
```

## Cost Optimization

### Development/Testing
```hcl
use_vertex_rag = false  # Use local ChromaDB
min_instances  = 0      # Scale to zero
max_instances  = 1      # Single instance max
cpu_limit      = "1"    # Minimum CPU
memory_limit   = "512Mi" # Minimum memory
```

### Production
```hcl
use_vertex_rag = true   # Use Vertex AI
min_instances  = 1      # Always-on for low latency
max_instances  = 3      # Handle traffic spikes
cpu_limit      = "2"    # More responsive
memory_limit   = "1Gi"  # Handle larger requests
```

## Troubleshooting

### "API not enabled"
```bash
# Enable APIs manually first
gcloud services enable run.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

### "Permission denied"
```bash
# Ensure you have required roles
gcloud projects add-iam-policy-binding bcn-art-compass \
  --member="user:your-email@example.com" \
  --role="roles/editor"
```

### "Index deployment failed"
- Check that embeddings file exists: `generated/vertex_embeddings.jsonl`
- Verify embeddings format (one JSON object per line)
- Ensure dimensions match (768 for text-embedding-005)
- Check Vertex AI quotas in GCP console

### "Secret not found"
```bash
# Create secret first
echo -n 'YOUR_API_KEY' | gcloud secrets create google-api-key --data-file=-
```

## Migration from Existing Setup

If you have resources created via bash scripts, you can migrate to Terraform:

1. **Review existing resources**
   ```bash
   gcloud run services list
   gcloud ai indexes list --region=europe-southwest1
   ```

2. **Import into Terraform**
   ```bash
   # Import each resource (see examples above)
   ```

3. **Verify plan**
   ```bash
   terraform plan  # Should show "No changes" if import was complete
   ```

4. **Future changes via Terraform**
   ```bash
   # Now manage everything through Terraform
   terraform apply
   ```

## CI/CD Integration

Update `cloudbuild.yaml` to deploy using Terraform:

```yaml
steps:
  # Build and push image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/bcn-art-compass:$SHORT_SHA', '.']
  
  # Update Cloud Run with new image
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'bcn-art-compass'
      - '--image=gcr.io/$PROJECT_ID/bcn-art-compass:$SHORT_SHA'
      - '--region=europe-southwest1'
```

Terraform will manage the infrastructure, while Cloud Build handles image updates.

## Security Best Practices

1. **Never commit terraform.tfvars** - It may contain sensitive values
2. **Use Secret Manager** - For API keys and credentials
3. **Enable versioning** - On GCS state bucket
4. **Restrict IAM** - Grant minimum required permissions
5. **Review plans carefully** - Before applying changes

## Further Reading

- [Terraform Google Provider Docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Run Terraform Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service)
- [Vertex AI Index Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/vertex_ai_index)
- [GCP Best Practices](https://cloud.google.com/architecture/framework)
