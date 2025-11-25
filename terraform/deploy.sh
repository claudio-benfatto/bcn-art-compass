#!/bin/bash
# Quick deployment script using Terraform
# This is a convenience wrapper around terraform commands

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}BCN Art Compass - Terraform Deployment${NC}"
echo ""

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: terraform is not installed${NC}"
    echo "Install with: brew install terraform"
    exit 1
fi

# Check if authenticated
if ! gcloud auth application-default print-access-token &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GCP${NC}"
    echo "Run: gcloud auth application-default login"
    exit 1
fi

# Check if embeddings exist (for Vertex AI)
if [ ! -f "../generated/vertex_embeddings.jsonl" ]; then
    echo -e "${YELLOW}Warning: Embeddings file not found${NC}"
    echo "Generate embeddings with: uv run python scripts/vertex/precompute_embeddings.py"
    echo ""
    echo -e "${YELLOW}Deploying without Vertex AI (use_vertex_rag=false)${NC}"
    echo ""
fi

# Initialize if needed
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Initializing Terraform...${NC}"
    terraform init
    echo ""
fi

# Show plan
echo -e "${YELLOW}Generating deployment plan...${NC}"
terraform plan
echo ""

# Ask for confirmation
read -p "Apply these changes? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Apply
echo -e "${YELLOW}Applying changes...${NC}"
terraform apply -auto-approve

# Show outputs
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo -e "${GREEN}Outputs:${NC}"
terraform output

echo ""
echo -e "${GREEN}Cloud Run URL:${NC}"
terraform output -raw cloud_run_url
echo ""
