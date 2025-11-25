# Embeddings and App Updates with Terraform

## Understanding the Separation of Concerns

### What Terraform Manages
- **Infrastructure**: Cloud Run service, Vertex AI index/endpoint, GCS buckets, IAM
- **Configuration**: Environment variables, resource limits, scaling settings
- **Structure**: How components connect together

### What Terraform Does NOT Manage
- **Docker images**: Handled by Cloud Build / CI/CD
- **Embeddings data**: Generated and uploaded separately
- **Application code**: Deployed via container images

This separation allows you to:
- Update app code without touching infrastructure
- Regenerate embeddings without redeploying
- Change infrastructure without rebuilding containers

## Handling Embeddings

### Initial Embeddings Setup

When deploying Vertex AI for the first time:

```bash
# 1. Generate embeddings locally
uv run python scripts/vertex/precompute_embeddings.py
# Creates: generated/vertex_embeddings.jsonl

# 2. Deploy infrastructure with Terraform
cd terraform
terraform apply -var="use_vertex_rag=true"

# Terraform will:
# - Create GCS bucket
# - Upload embeddings file
# - Create Vertex AI index from embeddings
# - Deploy index to endpoint
```

### Updating Embeddings (New Events)

When you add new events to `data/events.yaml`:

**Option 1: Regenerate and Update Index (Recommended)**

```bash
# 1. Regenerate embeddings with new events
uv run python scripts/vertex/precompute_embeddings.py

# 2. Upload new embeddings to GCS
gsutil cp generated/vertex_embeddings.jsonl \
  gs://bcn-art-compass-vertex-embeddings/embeddings/vertex_embeddings.json

# 3. Update Vertex AI index
gcloud ai indexes update <INDEX_ID> \
  --metadata-file=index-metadata.json \
  --region=europe-southwest1

# Or use terraform taint to force recreation:
cd terraform
terraform taint google_vertex_ai_index.art_events
terraform apply
```

**Option 2: Terraform Refresh (Simple but recreates index)**

```bash
# 1. Regenerate embeddings
uv run python scripts/vertex/precompute_embeddings.py

# 2. Let Terraform detect the change
cd terraform
terraform apply

# Terraform will:
# - Detect embeddings file changed
# - Upload new version to GCS
# - Recreate the index (takes 30-60 min)
```

**Option 3: Manual GCS Update (Fast, no downtime)**

```bash
# 1. Generate new embeddings
uv run python scripts/vertex/precompute_embeddings.py

# 2. Upload directly to GCS
gsutil cp generated/vertex_embeddings.jsonl \
  gs://bcn-art-compass-vertex-embeddings/embeddings/vertex_embeddings.json

# 3. Trigger index update (via Vertex AI API or console)
# The index will automatically pick up changes
```

### Embeddings Workflow Automation

Create a script for easy updates:

```bash
#!/bin/bash
# scripts/update-embeddings.sh

set -e

echo "Regenerating embeddings..."
uv run python scripts/vertex/precompute_embeddings.py

echo "Uploading to GCS..."
gsutil cp generated/vertex_embeddings.jsonl \
  gs://bcn-art-compass-vertex-embeddings/embeddings/vertex_embeddings.json

echo "Embeddings updated! Index will refresh automatically."
```

## Handling App Updates

### Development Workflow

```bash
# 1. Make code changes
vim agents/recommender_agent.py

# 2. Test locally
source .venv/bin/activate
python cli.py

# 3. Commit changes
git add -A
git commit -m "feat: improve ranking logic"
git push origin main
```

### Deployment Options

#### Option A: Cloud Build (Automatic)

Set up trigger in GCP:
```bash
gcloud builds triggers create github \
  --repo-name=bcn-art-compass \
  --repo-owner=claudio-benfatto \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

Now every push to `main` automatically:
1. Builds new Docker image
2. Pushes to GCR
3. Deploys to Cloud Run

**No Terraform needed** - infrastructure stays the same!

#### Option B: Manual Build and Deploy

```bash
# 1. Build and push image
gcloud builds submit --config cloudbuild.yaml

# 2. Update Cloud Run (Terraform ignores this)
gcloud run deploy bcn-art-compass \
  --image gcr.io/bcn-art-compass/bcn-art-compass:latest \
  --region europe-southwest1

# Infrastructure managed by Terraform isn't affected
```

#### Option C: Using Terraform (Not Recommended for Apps)

```bash
# Update the docker_image variable
cd terraform
terraform apply -var="docker_image=gcr.io/bcn-art-compass/bcn-art-compass:new-tag"
```

**Why not recommended**: Mixing app deployment with infrastructure changes. Better to keep them separate.

## Recommended Workflows

### For MVP Development

**Local Only (No Cloud Costs)**
```bash
# Run everything locally
ollama serve
uv run python cli.py
```

### For Staging/Testing

**Cloud Run Only (Cheap)**
```bash
# 1. Deploy infrastructure once
cd terraform
terraform apply -var="use_vertex_rag=false"

# 2. Update app as needed
gcloud builds submit --config cloudbuild.yaml

# Cost: ~$5-10/month (pay per request)
```

### For Production

**Full Stack with Vertex AI**
```bash
# 1. Generate embeddings
uv run python scripts/vertex/precompute_embeddings.py

# 2. Deploy infrastructure
cd terraform
terraform apply -var="use_vertex_rag=true"

# 3. Set up auto-deploy
gcloud builds triggers create github ...

# Cost: ~$360/month (Vertex AI always-on)
```

## Common Scenarios

### Scenario 1: Just Code Changes

```bash
# Developer workflow
git commit -am "fix: bug fix"
git push

# If auto-deploy is set up, done!
# Otherwise:
gcloud builds submit --config cloudbuild.yaml
```

**Terraform**: Not needed ✅

### Scenario 2: New Events Added

```bash
# 1. Edit events
vim data/events.yaml

# 2. Update embeddings
./scripts/update-embeddings.sh

# 3. (Optional) Force index refresh
# Usually automatic, but if needed:
cd terraform
terraform taint google_storage_bucket_object.embeddings
terraform apply
```

**Terraform**: Optional, only for index refresh

### Scenario 3: Infrastructure Changes

```bash
# Example: Increase memory
cd terraform
terraform apply -var="memory_limit=1Gi"
```

**Terraform**: Required ✅

### Scenario 4: Scale Up for Traffic

```bash
# Increase max instances
cd terraform
terraform apply -var="max_instances=5"
```

**Terraform**: Required ✅

### Scenario 5: Environment Variable Change

```bash
# Update main.tf to add new env var
cd terraform
vim main.tf
terraform apply
```

**Terraform**: Required ✅

## Best Practices

### ✅ DO

1. **Use Cloud Build for app updates**
   - Fast, automatic, no Terraform needed
   - Separates app deployment from infrastructure

2. **Use Terraform for infrastructure**
   - Cloud Run configuration
   - Vertex AI setup
   - IAM roles
   - Scaling settings

3. **Version your embeddings**
   - Keep embeddings file in Git (if small)
   - Or use GCS versioning for history

4. **Test locally first**
   - Validate embeddings work with ChromaDB
   - Test app changes before deploying

5. **Use terraform plan**
   - Always preview infrastructure changes
   - Avoid accidental deletions

### ❌ DON'T

1. **Don't use Terraform for every app update**
   - Use Cloud Build instead
   - Terraform is for infrastructure, not code

2. **Don't manually change infrastructure**
   - Always go through Terraform
   - Manual changes cause drift

3. **Don't commit terraform.tfstate**
   - It contains secrets
   - Use remote state instead

4. **Don't recreate Vertex AI index frequently**
   - Takes 30-60 minutes
   - Costs money
   - Update in-place when possible

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build and Deploy
        run: |
          gcloud builds submit --config cloudbuild.yaml
```

This deploys app changes automatically. Infrastructure stays managed by Terraform.

## Terraform State Management

### Local Development (Current Setup)

```bash
# State stored locally in terraform.tfstate
cd terraform
terraform apply
git add terraform.tfstate  # DON'T DO THIS!
```

### Production Setup (Recommended)

```bash
# 1. Create state bucket
gsutil mb -l europe-southwest1 gs://bcn-art-compass-tfstate
gsutil versioning set on gs://bcn-art-compass-tfstate

# 2. Update main.tf
terraform {
  backend "gcs" {
    bucket = "bcn-art-compass-tfstate"
    prefix = "terraform/state"
  }
}

# 3. Migrate state
terraform init -migrate-state
```

Benefits:
- Team collaboration
- State locking
- Version history
- Secure storage

## Troubleshooting

### "Embeddings file not found"

```bash
# Generate embeddings first
uv run python scripts/vertex/precompute_embeddings.py

# Then run Terraform
cd terraform
terraform apply
```

### "Index already exists"

```bash
# Import existing index
terraform import google_vertex_ai_index.art_events \
  projects/bcn-art-compass/locations/europe-southwest1/indexes/<INDEX_ID>
```

### "Cloud Run deployed but old version"

```bash
# Rebuild and push new image
gcloud builds submit --config cloudbuild.yaml

# Verify deployment
gcloud run revisions list --service=bcn-art-compass --region=europe-southwest1
```

### "Terraform wants to replace everything"

```bash
# Check what changed
terraform plan

# If unexpected, check for drift
terraform refresh
terraform plan
```

## Cost Optimization Tips

1. **Scale to zero when not in use**
   ```hcl
   min_instances = 0
   ```

2. **Disable Vertex AI in dev**
   ```hcl
   use_vertex_rag = false
   ```

3. **Use smaller machines**
   ```hcl
   cpu_limit = "1"
   memory_limit = "512Mi"
   ```

4. **Set lifecycle policies on GCS**
   - Already configured in Terraform
   - Deletes old versions after 30 days

## Quick Reference

| Task | Tool | Command |
|------|------|---------|
| Update app code | Cloud Build | `gcloud builds submit` |
| Update embeddings | Script + GCS | `./scripts/update-embeddings.sh` |
| Change infrastructure | Terraform | `terraform apply` |
| Scale service | Terraform | `terraform apply -var="max_instances=5"` |
| Add environment variable | Terraform | Edit `main.tf`, then `terraform apply` |
| Update secrets | gcloud | `gcloud secrets versions add` |
| Check current state | Terraform | `terraform show` |
| Preview changes | Terraform | `terraform plan` |

## Summary

**Golden Rule**: 
- 🐳 **Docker images** → Cloud Build
- 📊 **Embeddings** → Direct GCS upload or scripted
- 🏗️ **Infrastructure** → Terraform

Keep them separate for maximum flexibility and minimum complexity!
