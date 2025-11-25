#!/bin/bash
# Destroy all existing BCN Art Compass infrastructure
# Use this to clean up manually-created resources before using Terraform

set -e

PROJECT_ID="bcn-art-compass"
REGION="europe-southwest1"
SERVICE_NAME="bcn-art-compass"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}BCN Art Compass - Infrastructure Cleanup${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo -e "${YELLOW}This will DELETE all infrastructure:${NC}"
echo "  - Cloud Run service"
echo "  - Vertex AI deployed index"
echo "  - Vertex AI endpoint"
echo "  - Vertex AI index"
echo "  - GCS bucket (optional)"
echo ""
echo -e "${RED}⚠️  WARNING: This action is DESTRUCTIVE${NC}"
echo ""
read -p "Type 'DELETE' to confirm: " confirm

if [ "$confirm" != "DELETE" ]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo ""
echo -e "${YELLOW}Starting cleanup...${NC}"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# 1. Delete Cloud Run service
echo -e "${BLUE}[1/5] Checking Cloud Run service...${NC}"
if gcloud run services describe "$SERVICE_NAME" --region="$REGION" &>/dev/null; then
    echo -e "${YELLOW}Deleting Cloud Run service: $SERVICE_NAME${NC}"
    gcloud run services delete "$SERVICE_NAME" \
        --region="$REGION" \
        --quiet
    echo -e "${GREEN}✓ Cloud Run service deleted${NC}"
else
    echo -e "${GREEN}✓ Cloud Run service not found (already deleted)${NC}"
fi
echo ""

# 2. Undeploy index from endpoint
echo -e "${BLUE}[2/5] Checking Vertex AI deployed indexes...${NC}"
ENDPOINT_ID=$(gcloud ai index-endpoints list --region="$REGION" --format="value(name)" 2>/dev/null | head -1)
if [ -n "$ENDPOINT_ID" ]; then
    DEPLOYED_INDEX_ID=$(gcloud ai index-endpoints describe "$ENDPOINT_ID" \
        --region="$REGION" \
        --format="value(deployedIndexes[0].id)" 2>/dev/null)
    
    if [ -n "$DEPLOYED_INDEX_ID" ]; then
        echo -e "${YELLOW}Undeploying index: $DEPLOYED_INDEX_ID${NC}"
        gcloud ai index-endpoints undeploy-index "$ENDPOINT_ID" \
            --region="$REGION" \
            --deployed-index-id="$DEPLOYED_INDEX_ID" \
            --quiet
        
        echo "Waiting for undeployment to complete (this may take a few minutes)..."
        sleep 60
        echo -e "${GREEN}✓ Index undeployed${NC}"
    else
        echo -e "${GREEN}✓ No deployed indexes found${NC}"
    fi
else
    echo -e "${GREEN}✓ No endpoints found${NC}"
fi
echo ""

# 3. Delete endpoint
echo -e "${BLUE}[3/5] Checking Vertex AI endpoint...${NC}"
if [ -n "$ENDPOINT_ID" ]; then
    echo -e "${YELLOW}Deleting endpoint: $ENDPOINT_ID${NC}"
    gcloud ai index-endpoints delete "$ENDPOINT_ID" \
        --region="$REGION" \
        --quiet
    echo -e "${GREEN}✓ Endpoint deleted${NC}"
else
    echo -e "${GREEN}✓ Endpoint not found (already deleted)${NC}"
fi
echo ""

# 4. Delete index
echo -e "${BLUE}[4/5] Checking Vertex AI index...${NC}"
INDEX_ID=$(gcloud ai indexes list --region="$REGION" --format="value(name)" 2>/dev/null | head -1)
if [ -n "$INDEX_ID" ]; then
    echo -e "${YELLOW}Deleting index: $INDEX_ID${NC}"
    gcloud ai indexes delete "$INDEX_ID" \
        --region="$REGION" \
        --quiet
    echo -e "${GREEN}✓ Index deleted${NC}"
else
    echo -e "${GREEN}✓ Index not found (already deleted)${NC}"
fi
echo ""

# 5. Optionally delete GCS bucket
echo -e "${BLUE}[5/5] Checking GCS bucket...${NC}"
BUCKET_NAME="${PROJECT_ID}-vertex-embeddings"
if gsutil ls -b "gs://${BUCKET_NAME}" &>/dev/null; then
    echo ""
    echo -e "${YELLOW}GCS bucket exists: gs://${BUCKET_NAME}${NC}"
    echo "This bucket contains embeddings data."
    echo ""
    read -p "Delete bucket? (y/N): " delete_bucket
    
    if [ "$delete_bucket" = "y" ] || [ "$delete_bucket" = "Y" ]; then
        echo -e "${YELLOW}Deleting bucket...${NC}"
        gsutil -m rm -r "gs://${BUCKET_NAME}"
        echo -e "${GREEN}✓ Bucket deleted${NC}"
    else
        echo -e "${BLUE}✓ Bucket kept (you can delete it manually later)${NC}"
        echo "  To delete: gsutil rm -r gs://${BUCKET_NAME}"
    fi
else
    echo -e "${GREEN}✓ Bucket not found${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "All infrastructure has been removed."
echo ""
echo "What's still there (intentionally kept):"
echo "  • Secret Manager secret: google-api-key"
echo "  • Firestore data (if any)"
echo "  • GCS bucket (if you chose to keep it)"
echo ""
echo "To delete secrets:"
echo "  gcloud secrets delete google-api-key --quiet"
echo ""
echo "To start fresh with Terraform:"
echo "  cd terraform"
echo "  terraform init"
echo "  terraform apply"
echo ""
