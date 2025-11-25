#!/bin/bash
# Update Vertex AI embeddings without redeploying infrastructure
# This script regenerates embeddings and uploads them to GCS

set -e

PROJECT_ID="bcn-art-compass"
BUCKET_NAME="${PROJECT_ID}-vertex-embeddings"
EMBEDDINGS_FILE="generated/vertex_embeddings.jsonl"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Update Vertex AI Embeddings${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if events.yaml exists
if [ ! -f "data/events.yaml" ]; then
    echo -e "${YELLOW}Warning: data/events.yaml not found${NC}"
    exit 1
fi

# Step 1: Regenerate embeddings
echo -e "${YELLOW}[1/3] Regenerating embeddings from events.yaml...${NC}"
uv run python scripts/vertex/precompute_embeddings.py

if [ ! -f "$EMBEDDINGS_FILE" ]; then
    echo "Error: Failed to generate embeddings file"
    exit 1
fi

echo -e "${GREEN}✓ Embeddings generated${NC}"
echo ""

# Step 2: Check if bucket exists
echo -e "${YELLOW}[2/3] Checking GCS bucket...${NC}"
if ! gsutil ls -b "gs://${BUCKET_NAME}" &>/dev/null; then
    echo "Error: Bucket gs://${BUCKET_NAME} does not exist"
    echo "Run 'terraform apply' first to create infrastructure"
    exit 1
fi

echo -e "${GREEN}✓ Bucket exists${NC}"
echo ""

# Step 3: Upload to GCS
echo -e "${YELLOW}[3/3] Uploading embeddings to GCS...${NC}"
gsutil cp "$EMBEDDINGS_FILE" "gs://${BUCKET_NAME}/embeddings/vertex_embeddings.json"

echo -e "${GREEN}✓ Embeddings uploaded${NC}"
echo ""

# Show summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Embeddings Update Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Embeddings uploaded to: gs://${BUCKET_NAME}/embeddings/vertex_embeddings.json"
echo ""
echo "The Vertex AI index will automatically pick up the new embeddings."
echo "This may take a few minutes to fully propagate."
echo ""
echo "To force an immediate index refresh:"
echo "  cd terraform"
echo "  terraform taint google_vertex_ai_index.art_events"
echo "  terraform apply"
echo ""
