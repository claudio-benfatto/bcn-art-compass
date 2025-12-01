#!/bin/bash
#
# Deploy BCN Art Compass to Cloud Run with Vertex AI configuration
#
# This script updates an existing Cloud Run deployment to use Vertex AI Vector Search
#
# Usage: ./scripts/deploy_with_vertex.sh [DEPLOYED_INDEX_ID]

set -e

PROJECT_ID="bcn-art-compass"
REGION="europe-southwest1"
SERVICE_NAME="bcn-art-compass"

# Vertex AI configuration
# INDEX_ENDPOINT will be discovered dynamically from the Vertex endpoint
INDEX_ENDPOINT=""
DEPLOYED_INDEX_ID=${1:-}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Deploy to Cloud Run with Vertex AI${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Discover the Vertex AI index endpoint created by Terraform
echo -e "${YELLOW}Locating Vertex AI index endpoint...${NC}"
ENDPOINT_NAME=$(gcloud ai index-endpoints list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --filter="displayName:bcn-art-compass-endpoint" \
    --format="value(name)" 2>/dev/null || echo "")

if [ -z "$ENDPOINT_NAME" ]; then
    echo -e "${RED}Error: Vertex index endpoint 'bcn-art-compass-endpoint' not found in ${PROJECT_ID}/${REGION}${NC}"
    echo ""
    echo "Make sure you've run Terraform to create the Vertex index and endpoint, e.g.:"
    echo "  (cd terraform && ./deploy.sh)"
    exit 1
fi

INDEX_ENDPOINT="$ENDPOINT_NAME"

# Check if deployed index ID is provided; if not, poll until available
if [ -z "$DEPLOYED_INDEX_ID" ]; then
    echo -e "${YELLOW}Checking for deployed index...${NC}"

    # Helper to query the current deployed index id from the endpoint
    get_deployed_index_id() {
        gcloud ai index-endpoints describe "$INDEX_ENDPOINT" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --format="value(deployedIndexes[0].id)" 2>/dev/null || echo ""
    }

    DEPLOYED_INDEX_ID="$(get_deployed_index_id)"

    if [ -z "$DEPLOYED_INDEX_ID" ]; then
        echo -e "${YELLOW}No deployed index found yet. Tracking status (Ctrl+C to abort)...${NC}"
        echo ""
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        ROOT_DIR="${SCRIPT_DIR}/.."

        # Loop until an index is deployed
        while [ -z "$DEPLOYED_INDEX_ID" ]; do
            # Show current Vertex status (non-fatal if the script fails)
            if [ -x "${ROOT_DIR}/vertex/check_vertex_status.sh" ]; then
                "${ROOT_DIR}/vertex/check_vertex_status.sh" "$PROJECT_ID" "$REGION" || true
            else
                echo -e "${YELLOW}(Vertex status script not found at ${ROOT_DIR}/vertex/check_vertex_status.sh)${NC}"
            fi

            echo ""
            echo -e "${YELLOW}Waiting for deployed index on endpoint ${INDEX_ENDPOINT}...${NC}"
            sleep 30

            DEPLOYED_INDEX_ID="$(get_deployed_index_id)"
        done
    fi

    echo -e "${GREEN}✓ Found deployed index: ${DEPLOYED_INDEX_ID}${NC}"
fi

echo ""
echo -e "  Project:           ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Region:            ${GREEN}${REGION}${NC}"
echo -e "  Service:           ${GREEN}${SERVICE_NAME}${NC}"
echo -e "  Index Endpoint:    ${GREEN}${INDEX_ENDPOINT}${NC}"
echo -e "  Deployed Index ID: ${GREEN}${DEPLOYED_INDEX_ID}${NC}"
echo ""

# Build and deploy
echo -e "${YELLOW}Building and deploying with Vertex AI configuration...${NC}"

gcloud builds submit --config cloudbuild.yaml \
    --project="$PROJECT_ID" \
    --substitutions="_DEPLOY_REGION=${REGION},_IMAGE_TAG=vertex-$(date +%s)"

echo ""
echo -e "${YELLOW}Updating Cloud Run environment variables...${NC}"

# Get GOOGLE_API_KEY from .env if not in environment
if [ -z "$GOOGLE_API_KEY" ]; then
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | grep GOOGLE_API_KEY | xargs)
    fi
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${RED}Error: GOOGLE_API_KEY not found in environment or .env file${NC}"
    echo "Please set GOOGLE_API_KEY environment variable or add it to .env file"
    exit 1
fi

gcloud run services update "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --update-env-vars="USE_VERTEX_RAG=true" \
    --update-env-vars="VERTEX_INDEX_ENDPOINT=${INDEX_ENDPOINT}" \
    --update-env-vars="VERTEX_DEPLOYED_INDEX_ID=${DEPLOYED_INDEX_ID}"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(status.url)")

echo -e "Service URL: ${BLUE}${SERVICE_URL}${NC}"
echo ""
echo "Test the service:"
echo ""
echo -e "  ${YELLOW}curl -X POST ${SERVICE_URL}/chat \\${NC}"
echo -e "    ${YELLOW}-H 'Content-Type: application/json' \\${NC}"
echo -e "    ${YELLOW}-d '{\"message\": \"Find art exhibitions in Barcelona\", \"user_id\": \"test\"}'${NC}"
echo ""
