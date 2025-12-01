# Quick Reference: Terraform Workflows

## Daily Development

### Update App Code
```bash
# 1. Make changes
vim agents/recommender_agent.py

# 2. Test locally
uv run python cli.py

# 3. Deploy
gcloud builds submit --config cloudbuild.yaml
```
**No Terraform needed** ✅

### Add New Events
```bash
# 1. Edit events
vim data/events.yaml

# 2. Update embeddings (if using Vertex AI)
./scripts/update-embeddings.sh
```
**No Terraform needed** ✅

## Infrastructure Changes

### Scale Up/Down
```bash
cd terraform
terraform apply -var="max_instances=5"
```

### Change Resources
```bash
cd terraform
terraform apply -var="memory_limit=1Gi" -var="cpu_limit=2"
```

### Add Environment Variable
```bash
# 1. Edit main.tf
vim terraform/main.tf

# 2. Apply
cd terraform
terraform apply
```

## Deployment Stages

### Stage 1: Local Development
```bash
# Zero cost, full functionality
uv run python cli.py
```

### Stage 2: Cloud Testing
```bash
# One-time infrastructure setup
cd terraform
terraform apply -var="use_vertex_rag=false"

# Deploy app updates
gcloud builds submit --config cloudbuild.yaml
```

### Stage 3: Production
```bash
# One-time infrastructure setup with Vertex AI
./scripts/update-embeddings.sh
cd terraform
terraform apply -var="use_vertex_rag=true"

# Deploy app updates
gcloud builds submit --config cloudbuild.yaml
```

## Key Commands

```bash
# Preview changes
terraform plan

# Apply changes
terraform apply

# Show current state
terraform show

# Get outputs
terraform output cloud_run_url

# Force recreate resource
terraform taint google_cloud_run_v2_service.bcn_art_compass
terraform apply

# Update embeddings (without Terraform)
./scripts/update-embeddings.sh

# Deploy new app version (without Terraform)
gcloud builds submit --config cloudbuild.yaml
```

## What Uses What

| Task | Tool | Why |
|------|------|-----|
| Code changes | Cloud Build | Fast, automatic |
| Embeddings updates | GCS script | No infrastructure change |
| Scaling | Terraform | Infrastructure config |
| Environment vars | Terraform | Infrastructure config |
| IAM roles | Terraform | Infrastructure config |

## Remember

**Terraform = Infrastructure** (Cloud Run config, Vertex AI, IAM)  
**Cloud Build = Application** (Docker images, code updates)  
**Scripts = Data** (Embeddings updates)

Keep them separate for simplicity!
