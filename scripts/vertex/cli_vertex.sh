#!/bin/bash
#
# Run BCN Art Compass CLI with Vertex AI Vector Search
#
# This script configures the CLI to use the cloud-deployed Vertex AI backend
# instead of the local ChromaDB.
#
# Prerequisites:
# - gcloud auth application-default login (for authentication)
# - Vertex AI index deployed and accessible
#

set -e

PROJECT_ID="bcn-art-compass"
LOCATION="europe-southwest1"
INDEX_ENDPOINT="projects/877857922566/locations/europe-southwest1/indexEndpoints/5092533239579410432"
DEPLOYED_INDEX_ID="bcn_art_compass_1763822114"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}BCN Art Compass CLI - Vertex AI Mode${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check authentication
echo -e "${YELLOW}Checking authentication...${NC}"
if ! gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo -e "${YELLOW}Setting up Application Default Credentials...${NC}"
    echo ""
    gcloud auth application-default login
    echo ""
fi

echo -e "${GREEN}✓ Authenticated${NC}"
echo -e "  Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Location: ${GREEN}${LOCATION}${NC}"
echo -e "  Backend: ${GREEN}Vertex AI Vector Search${NC}"
echo ""

# Check for GOOGLE_API_KEY
if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${YELLOW}Note: GOOGLE_API_KEY not set in environment${NC}"
    if [ -f ".env" ]; then
        echo -e "${YELLOW}Loading from .env file...${NC}"
        export $(grep -v '^#' .env | grep GOOGLE_API_KEY | xargs)
    fi
    
    if [ -z "$GOOGLE_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  Fetching GOOGLE_API_KEY from Cloud Run service...${NC}"
        export GOOGLE_API_KEY=$(gcloud run services describe bcn-art-compass \
            --region europe-southwest1 \
            --format=json 2>/dev/null | \
            jq -r '.spec.template.spec.containers[0].env[] | select(.name=="GOOGLE_API_KEY") | .value')
        
        if [ -z "$GOOGLE_API_KEY" ]; then
            echo -e "${YELLOW}⚠️  Warning: GOOGLE_API_KEY still not found${NC}"
            echo -e "${YELLOW}Embeddings will fail. Please set GOOGLE_API_KEY environment variable.${NC}"
            echo ""
        else
            echo -e "${GREEN}✓ API key retrieved from Cloud Run${NC}"
        fi
    fi
fi

# Run CLI with Vertex AI configuration
export USE_VERTEX_RAG=true
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="$LOCATION"
export VERTEX_INDEX_ENDPOINT="$INDEX_ENDPOINT"
export VERTEX_DEPLOYED_INDEX_ID="$DEPLOYED_INDEX_ID"

cd "$(dirname "$0")/.."
PYTHONPATH=$PWD uv run python cli.py
