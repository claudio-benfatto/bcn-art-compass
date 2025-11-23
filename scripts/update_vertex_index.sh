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
INDEX_ID="8363378022073499648"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Update Vertex AI Index${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Step 1: Regenerate embeddings
echo -e "${YELLOW}Step 1: Generating embeddings from events.yaml...${NC}"
rm -f vertex_embeddings.jsonl
uv run ./scripts/prepare_vertex_data.py

if [ ! -f vertex_embeddings.jsonl ]; then
    echo "Error: Failed to generate embeddings"
    exit 1
fi

EVENT_COUNT=$(wc -l < vertex_embeddings.jsonl | tr -d ' ')
echo -e "${GREEN}✓ Generated embeddings for ${EVENT_COUNT} events${NC}"
echo ""

# Step 2: Upload to GCS
echo -e "${YELLOW}Step 2: Uploading embeddings to GCS...${NC}"
JSON_FILE="vertex_embeddings.json"
gsutil cp vertex_embeddings.jsonl "gs://${BUCKET_NAME}/embeddings/${JSON_FILE}"
echo -e "${GREEN}✓ Uploaded to gs://${BUCKET_NAME}/embeddings/${JSON_FILE}${NC}"
echo ""

# Step 3: Update index
echo -e "${YELLOW}Step 3: Updating Vertex AI index...${NC}"
echo -e "${BLUE}This will trigger an index rebuild (takes 5-10 minutes)${NC}"
echo ""

gcloud ai indexes update ${INDEX_ID} \
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
echo "  ./scripts/check_vertex_status.sh"
echo ""
echo "The index will be ready in 5-10 minutes."
echo "No need to redeploy Cloud Run - it will automatically use the updated index."
echo ""
