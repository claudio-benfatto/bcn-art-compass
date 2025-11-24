#!/bin/bash
#
# Setup Vertex AI Vector Search for BCN Art Compass
#
# This script:
# 1. Enables required APIs
# 2. Creates a GCS bucket for embeddings
# 3. Uploads embedding data
# 4. Creates a Vertex AI Vector Search index
# 5. Deploys the index to an endpoint
#
# Usage: ./scripts/setup_vertex_ai.sh PROJECT_ID REGION

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
PROJECT_ID=${1:-}
REGION=${2:-europe-southwest1}
INDEX_DISPLAY_NAME="bcn-art-compass-index"
ENDPOINT_DISPLAY_NAME="bcn-art-compass-endpoint"
BUCKET_NAME="${PROJECT_ID}-vertex-embeddings"
EMBEDDINGS_FILE="generated/vertex_embeddings.jsonl"

# Validate arguments
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID is required${NC}"
    echo "Usage: $0 PROJECT_ID [REGION]"
    echo "Example: $0 bcn-art-compass europe-southwest1"
    exit 1
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Vertex AI Vector Search Setup${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "  Project ID:      ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Region:          ${GREEN}${REGION}${NC}"
echo -e "  Index Name:      ${GREEN}${INDEX_DISPLAY_NAME}${NC}"
echo -e "  Endpoint Name:   ${GREEN}${ENDPOINT_DISPLAY_NAME}${NC}"
echo -e "  Bucket:          ${GREEN}${BUCKET_NAME}${NC}"
echo ""

# Set project
echo -e "${YELLOW}Setting project...${NC}"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable \
    aiplatform.googleapis.com \
    storage.googleapis.com \
    --project="$PROJECT_ID"

echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Prepare embedding data
echo -e "${YELLOW}Preparing embedding data...${NC}"
if [ ! -f "$EMBEDDINGS_FILE" ]; then
    echo "Generating embeddings from events.yaml..."
    uv run ./scripts/prepare_vertex_data.py
fi

if [ ! -f "$EMBEDDINGS_FILE" ]; then
    echo -e "${RED}Error: $EMBEDDINGS_FILE not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Embedding data ready${NC}"
echo ""

# Create GCS bucket
echo -e "${YELLOW}Creating GCS bucket: gs://${BUCKET_NAME}${NC}"
if gsutil ls -b "gs://${BUCKET_NAME}" 2>/dev/null; then
    echo -e "${BLUE}Bucket already exists${NC}"
else
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${BUCKET_NAME}"
    echo -e "${GREEN}✓ Bucket created${NC}"
fi
echo ""

# Upload embeddings to GCS (rename to .json for Vertex AI)
echo -e "${YELLOW}Uploading embeddings to GCS...${NC}"
JSON_FILE="vertex_embeddings.json"
gsutil cp "$EMBEDDINGS_FILE" "gs://${BUCKET_NAME}/embeddings/${JSON_FILE}"
echo -e "${GREEN}✓ Embeddings uploaded to gs://${BUCKET_NAME}/embeddings/${JSON_FILE}${NC}"
echo ""

# Get embedding dimensions
echo -e "${YELLOW}Detecting embedding dimensions...${NC}"
DIMENSIONS=$(head -n 1 "$EMBEDDINGS_FILE" | uv run python -c "import sys, json; print(len(json.load(sys.stdin)['embedding']))")
echo -e "${GREEN}✓ Detected ${DIMENSIONS} dimensions${NC}"
echo ""

# Create Vertex AI Vector Search Index
echo -e "${YELLOW}Creating Vertex AI Vector Search index...${NC}"
echo -e "${BLUE}This may take 20-30 minutes...${NC}"

# Check if index already exists
EXISTING_INDEX=$(gcloud ai indexes list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --filter="displayName:${INDEX_DISPLAY_NAME}" \
    --format="value(name)" 2>/dev/null || echo "")

if [ -n "$EXISTING_INDEX" ]; then
    echo -e "${BLUE}Index already exists: ${EXISTING_INDEX}${NC}"
    INDEX_ID="$EXISTING_INDEX"
else
    # Create index
    INDEX_ID=$(gcloud ai indexes create \
        --display-name="$INDEX_DISPLAY_NAME" \
        --description="Event embeddings for BCN Art Compass" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --metadata-file=<(cat <<EOF
{
  "contentsDeltaUri": "gs://${BUCKET_NAME}/embeddings/",
  "config": {
    "dimensions": ${DIMENSIONS},
    "approximateNeighborsCount": 10,
    "distanceMeasureType": "DOT_PRODUCT_DISTANCE",
    "algorithmConfig": {
      "treeAhConfig": {
        "leafNodeEmbeddingCount": 1000,
        "leafNodesToSearchPercent": 5
      }
    }
  }
}
EOF
    ) \
        --format="value(name)")
    
    echo -e "${GREEN}✓ Index created: ${INDEX_ID}${NC}"
fi
echo ""

# Wait for index to be ready
echo -e "${YELLOW}Waiting for index to be ready...${NC}"
while true; do
    STATE=$(gcloud ai indexes describe "$INDEX_ID" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(deployedIndexes[0].indexState)" 2>/dev/null || echo "")
    
    if [ "$STATE" = "DEPLOYED" ]; then
        echo -e "${GREEN}✓ Index is ready${NC}"
        break
    fi
    
    echo -e "${BLUE}Current state: ${STATE}. Waiting...${NC}"
    sleep 30
done
echo ""

# Create Index Endpoint
echo -e "${YELLOW}Creating Index Endpoint...${NC}"

EXISTING_ENDPOINT=$(gcloud ai index-endpoints list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --filter="displayName:${ENDPOINT_DISPLAY_NAME}" \
    --format="value(name)" 2>/dev/null || echo "")

if [ -n "$EXISTING_ENDPOINT" ]; then
    echo -e "${BLUE}Endpoint already exists: ${EXISTING_ENDPOINT}${NC}"
    ENDPOINT_ID="$EXISTING_ENDPOINT"
else
    ENDPOINT_ID=$(gcloud ai index-endpoints create \
        --display-name="$ENDPOINT_DISPLAY_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --public-endpoint-enabled \
        --format="value(name)")
    
    echo -e "${GREEN}✓ Endpoint created: ${ENDPOINT_ID}${NC}"
fi
echo ""

# Deploy Index to Endpoint
echo -e "${YELLOW}Deploying index to endpoint...${NC}"
echo -e "${BLUE}This may take 10-15 minutes...${NC}"

DEPLOYED_INDEX_ID="bcn_art_compass_deployed_$(date +%s)"

gcloud ai index-endpoints deploy-index "$ENDPOINT_ID" \
    --deployed-index-id="$DEPLOYED_INDEX_ID" \
    --display-name="$DEPLOYED_INDEX_ID" \
    --index="$INDEX_ID" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --min-replica-count=1 \
    --max-replica-count=1 \
    --machine-type=e2-standard-2

echo -e "${GREEN}✓ Index deployed to endpoint${NC}"
echo ""

# Get endpoint details
ENDPOINT_RESOURCE_NAME=$(gcloud ai index-endpoints describe "$ENDPOINT_ID" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(name)")

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Vertex AI Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "Add these to your Cloud Run environment variables:"
echo ""
echo -e "${BLUE}VERTEX_INDEX_ENDPOINT:${NC} ${ENDPOINT_RESOURCE_NAME}"
echo -e "${BLUE}VERTEX_DEPLOYED_INDEX_ID:${NC} ${DEPLOYED_INDEX_ID}"
echo -e "${BLUE}USE_VERTEX_RAG:${NC} true"
echo ""
echo "Update cloudbuild.yaml and redeploy:"
echo ""
echo -e "${YELLOW}./scripts/deploy.sh ${PROJECT_ID} ${REGION}${NC}"
echo ""
