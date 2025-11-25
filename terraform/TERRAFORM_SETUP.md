# Terraform Infrastructure Setup - Summary

## What Was Created

A complete Terraform configuration to manage all BCN Art Compass infrastructure on Google Cloud Platform.

### Files Created

```
terraform/
├── main.tf                    # Main infrastructure definitions
├── variables.tf               # Configuration variables
├── outputs.tf                 # Output values after deployment
├── terraform.tfvars.example   # Example configuration
├── .gitignore                 # Ignore state files and secrets
├── README.md                  # Comprehensive documentation
├── MIGRATION.md               # Migration guide from bash scripts
└── deploy.sh                  # Quick deployment wrapper script
```

## Infrastructure Managed

### ✅ Cloud Run Service
- Auto-scaling configuration (0-1 instances)
- Service account with appropriate IAM roles
- Environment variables (project, region, feature flags)
- Secret management (Google API key)
- Health checks and probes
- Resource limits (512Mi memory, 1 CPU)

### ✅ Vertex AI Vector Search
- Vector index for event embeddings (768 dimensions)
- Index endpoint for queries
- Deployed index configuration
- GCS bucket for embeddings storage
- Configurable via `use_vertex_rag` variable

### ✅ Supporting Services
- Secret Manager for API keys
- Artifact Registry for Docker images
- GCS bucket with lifecycle policies
- IAM roles and service accounts
- API enablement

## Key Features

### 1. Declarative Infrastructure
```hcl
# Define what you want, Terraform handles how
resource "google_cloud_run_v2_service" "bcn_art_compass" {
  name     = "bcn-art-compass"
  location = "europe-southwest1"
  # ... rest of configuration
}
```

### 2. State Management
- Tracks all resources
- Detects drift from desired state
- Enables safe updates and rollbacks
- Supports remote state for team collaboration

### 3. Plan Before Apply
```bash
terraform plan  # Preview changes
terraform apply # Apply after review
```

### 4. Dependency Management
- Automatic resource ordering
- Parallel creation where possible
- Proper cleanup on destroy

### 5. Environment Variables
Easily configure different environments:
```hcl
# Development
use_vertex_rag = false
min_instances  = 0
max_instances  = 1

# Production
use_vertex_rag = true
min_instances  = 1
max_instances  = 3
```

## Usage

### Quick Start
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### With Custom Configuration
```bash
# Copy and edit tfvars
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars

# Apply with your config
terraform apply
```

### Deploy Script
```bash
cd terraform
./deploy.sh
```

## Integration with Existing Workflow

### Cloud Build (CI/CD)
Your existing `cloudbuild.yaml` continues to work:
- Builds Docker images
- Pushes to GCR
- Updates Cloud Run with new image

Terraform manages:
- Cloud Run service configuration
- All other infrastructure

### Bash Scripts
Can be archived or kept for reference:
- `scripts/deploy-to-cloud-run.sh` → Replaced by Terraform
- `scripts/vertex/setup_vertex_ai.sh` → Replaced by Terraform
- `scripts/vertex/check_vertex_status.sh` → Can use `terraform show`

## Migration Path

Two options:

### Option 1: Import Existing Resources
```bash
terraform import google_cloud_run_v2_service.bcn_art_compass \
  projects/bcn-art-compass/locations/europe-southwest1/services/bcn-art-compass
```
Keeps existing resources, brings under Terraform management.

### Option 2: Fresh Deployment
```bash
# Destroy old resources manually
# Deploy with Terraform
terraform apply
```

See `terraform/MIGRATION.md` for detailed instructions.

## Cost Optimization

### Development (Minimal Cost)
```hcl
use_vertex_rag = false  # Local ChromaDB instead
min_instances  = 0      # Scale to zero
max_instances  = 1      # Single instance
memory_limit   = "512Mi"
```

**Estimated cost**: ~$5-10/month (mostly Cloud Run requests)

### Production (With Vertex AI)
```hcl
use_vertex_rag = true   # Vertex AI Vector Search
min_instances  = 1      # Always-on
max_instances  = 3      # Handle spikes
memory_limit   = "1Gi"
```

**Estimated cost**: ~$360/month ($0.50/hour for Vertex AI n1-standard-2)

## Outputs

After deployment, get important values:
```bash
terraform output cloud_run_url
terraform output vertex_endpoint_domain
terraform output deployed_index_id
```

## Benefits Over Bash Scripts

| Feature | Bash Scripts | Terraform |
|---------|--------------|-----------|
| **Idempotency** | ❌ Manual checks | ✅ Automatic |
| **State Tracking** | ❌ None | ✅ Full state |
| **Preview Changes** | ❌ No | ✅ terraform plan |
| **Rollback** | ❌ Manual | ✅ Easy |
| **Dependencies** | ❌ Manual ordering | ✅ Automatic |
| **Drift Detection** | ❌ No | ✅ Yes |
| **Team Collaboration** | ❌ Difficult | ✅ Remote state |
| **Version Control** | ⚠️ Scripts only | ✅ Complete IaC |

## Security Best Practices

1. **Never commit secrets**
   - `terraform.tfvars` is git-ignored
   - Use Secret Manager for sensitive values

2. **Use remote state with versioning**
   ```bash
   gsutil versioning set on gs://terraform-state-bucket
   ```

3. **Restrict IAM permissions**
   - Grant minimum required roles
   - Use service accounts

4. **Review plans carefully**
   ```bash
   terraform plan | tee plan.txt
   # Review plan.txt before applying
   ```

## Next Steps

1. **Initial Setup**
   ```bash
   cd terraform
   terraform init
   terraform apply -var="use_vertex_rag=false"
   ```

2. **Test Deployment**
   ```bash
   CLOUD_RUN_URL=$(terraform output -raw cloud_run_url)
   curl "${CLOUD_RUN_URL}/health"
   ```

3. **Enable Remote State** (for team)
   ```bash
   gsutil mb gs://bcn-art-compass-terraform-state
   # Uncomment backend block in main.tf
   terraform init -migrate-state
   ```

4. **Enable Vertex AI** (when ready)
   ```bash
   terraform apply -var="use_vertex_rag=true"
   ```

5. **Set Up CI/CD Integration**
   - Cloud Build handles image updates
   - Terraform manages infrastructure changes

## Troubleshooting

### Common Issues

**"API not enabled"**
```bash
gcloud services enable run.googleapis.com aiplatform.googleapis.com
```

**"Secret not found"**
```bash
echo -n 'YOUR_API_KEY' | gcloud secrets create google-api-key --data-file=-
```

**"Embeddings file not found"**
```bash
uv run python scripts/vertex/precompute_embeddings.py
```

**"Permission denied"**
```bash
gcloud auth application-default login
gcloud config set project bcn-art-compass
```

### Getting Help

1. Check `terraform/README.md` for detailed docs
2. Use `terraform plan` to preview changes
3. Check state: `terraform state list`
4. Validate config: `terraform validate`
5. Format code: `terraform fmt`

## Resources

- **Main Config**: `terraform/main.tf`
- **Documentation**: `terraform/README.md`
- **Migration Guide**: `terraform/MIGRATION.md`
- **Example Config**: `terraform/terraform.tfvars.example`
- **Terraform Docs**: https://registry.terraform.io/providers/hashicorp/google/latest/docs

## Comparison: Before and After

### Before (Bash Scripts)
```bash
# Deploy Cloud Run
./scripts/deploy-to-cloud-run.sh

# Setup Vertex AI
./scripts/vertex/setup_vertex_ai.sh bcn-art-compass europe-southwest1

# Check status
./scripts/vertex/check_vertex_status.sh

# Manual tracking of what's deployed
# No easy way to preview changes
# Difficult to rollback
```

### After (Terraform)
```bash
# Deploy everything
cd terraform
terraform apply

# Preview changes
terraform plan

# Check current state
terraform show

# Get outputs
terraform output

# Rollback if needed
terraform apply  # Reverts to tfstate
```

## Maintenance

### Regular Tasks

**Update infrastructure**
```bash
# Edit main.tf or variables
terraform plan
terraform apply
```

**Update Docker image** (via Cloud Build)
```bash
gcloud builds submit --config cloudbuild.yaml
# Or let CI/CD handle it
```

**Check for drift**
```bash
terraform plan  # Shows if manual changes were made
```

**Update Terraform**
```bash
brew upgrade terraform
terraform init -upgrade
```

## Conclusion

You now have a complete, production-ready Terraform configuration that:

✅ Manages all infrastructure declaratively  
✅ Provides state tracking and rollback capability  
✅ Enables team collaboration via remote state  
✅ Integrates with existing CI/CD workflows  
✅ Optimizes costs with configurable scaling  
✅ Supports both local dev and Vertex AI production  
✅ Includes comprehensive documentation  

The migration from bash scripts to Terraform provides better reliability, reproducibility, and maintainability for your infrastructure.
