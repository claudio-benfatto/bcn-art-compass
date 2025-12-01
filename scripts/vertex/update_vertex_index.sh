#!/bin/bash
#
# Update Vertex AI index with new events
#
# This script regenerates embeddings from events.yaml and updates the Vertex AI index
#
# Usage: ./scripts/update_vertex_index.sh

set -e

PROJECT_ID="bcn-art-compass"
REGION="europe-southwest1"
BUCKET_NAME="${PROJECT_ID}-vertex-embeddings"
INDEX_ID=""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Update Vertex AI Index${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Discover Vertex AI index ID by display name (created by Terraform)
echo -e "${YELLOW}Locating Vertex AI index...${NC}"
INDEX_ID=$(gcloud ai indexes list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --filter="displayName=bcn-art-compass-index" \
    --format="value(name)" 2>/dev/null || echo "")

if [ -z "$INDEX_ID" ]; then
    echo -e "${RED}Error: Vertex index 'bcn-art-compass-index' not found in ${PROJECT_ID}/${REGION}${NC}"
    echo ""
    echo "Make sure you've run Terraform to create the Vertex index, e.g.:"
    echo "  (cd terraform && ./deploy.sh)"
    exit 1
fi

echo -e "${GREEN}✓ Found index: ${INDEX_ID}${NC}"
echo ""

# Step 1: Regenerate embeddings
echo -e "${YELLOW}Step 1: Generating embeddings from events.yaml...${NC}"
rm -f generated/vertex_embeddings.jsonl
uv run ./scripts/data/prepare_vertex_data.py

if [ ! -f generated/vertex_embeddings.jsonl ]; then
    echo "Error: Failed to generate embeddings"
    exit 1
fi

EVENT_COUNT=$(wc -l < generated/vertex_embeddings.jsonl | tr -d ' ')
echo -e "${GREEN}✓ Generated embeddings for ${EVENT_COUNT} events${NC}"
echo ""

# Step 2: Upload to GCS
echo -e "${YELLOW}Step 2: Uploading embeddings to GCS...${NC}"
JSON_FILE="vertex_embeddings.json"
gsutil cp generated/vertex_embeddings.jsonl "gs://${BUCKET_NAME}/embeddings/${JSON_FILE}"
echo -e "${GREEN}✓ Uploaded to gs://${BUCKET_NAME}/embeddings/${JSON_FILE}${NC}"
echo ""

# Step 3: Update index
echo -e "${YELLOW}Step 3: Updating Vertex AI index...${NC}"
echo -e "${BLUE}This will trigger an index rebuild (takes 5-10 minutes)${NC}"
echo ""

gcloud ai indexes update "${INDEX_ID}" \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --metadata-file=<(cat <<EOF
{
  "contentsDeltaUri": "gs://${BUCKET_NAME}/embeddings/",
  "isCompleteOverwrite": true
}
EOF
)

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Index Update Initiated!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Monitor progress with:"
echo "  ./scripts/vertex/check_vertex_status.sh"
echo ""
echo "The index will be ready in 5-10 minutes."
echo "No need to redeploy Cloud Run - it will automatically use the updated index."
echo ""
