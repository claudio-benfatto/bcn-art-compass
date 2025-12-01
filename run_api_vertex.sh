#!/bin/bash
#
# Run BCN Art Compass API with Vertex AI Vector Search
#
# This script configures the API server to use the cloud-deployed Vertex AI backend
# instead of the local ChromaDB.
#
# Prerequisites:
# - gcloud auth application-default login (for authentication)
# - Vertex AI index deployed and accessible
# - Valid GOOGLE_API_KEY for Gemini LLM calls
#

set -e

PROJECT_ID="bcn-art-compass"
LOCATION="europe-southwest1"
# These will be discovered dynamically from Vertex AI if not set explicitly
INDEX_ENDPOINT=""
DEPLOYED_INDEX_ID=""

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}BCN Art Compass API - Vertex AI Mode${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check authentication
echo -e "${YELLOW}Checking authentication...${NC}"
if ! gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo -e "${YELLOW}Setting up Application Default Credentials...${NC}"
    echo ""
    echo "This will open a browser window for authentication."
    echo "Please log in with your Google Cloud account."
    echo ""
    gcloud auth application-default login --project="$PROJECT_ID"
    echo ""
fi

echo -e "${GREEN}✓ Authenticated${NC}"
echo -e "  Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Location: ${GREEN}${LOCATION}${NC}"
echo ""

# Discover Vertex AI index endpoint (created by Terraform) if not provided
if [ -z "$INDEX_ENDPOINT" ]; then
  echo -e "${YELLOW}Discovering Vertex AI index endpoint...${NC}"
  ENDPOINT_NAME=$(gcloud ai index-endpoints list \
      --region="$LOCATION" \
      --project="$PROJECT_ID" \
      --filter="displayName:bcn-art-compass-endpoint" \
      --format="value(name)" 2>/dev/null || echo "")

  if [ -z "$ENDPOINT_NAME" ]; then
      echo -e "${RED}Error: Vertex index endpoint 'bcn-art-compass-endpoint' not found in ${PROJECT_ID}/${LOCATION}${NC}"
      echo ""
      echo "Make sure you've run Terraform to create the Vertex index and endpoint, e.g.:"
      echo "  (cd terraform && terraform apply)"
      exit 1
  fi

  INDEX_ENDPOINT="$ENDPOINT_NAME"
fi

# Discover deployed index ID if not explicitly set
if [ -z "$DEPLOYED_INDEX_ID" ]; then
  echo -e "${YELLOW}Checking for deployed index on endpoint...${NC}"
  DEPLOYED_INDEX_ID=$(gcloud ai index-endpoints describe "$INDEX_ENDPOINT" \
      --region="$LOCATION" \
      --project="$PROJECT_ID" \
      --format="value(deployedIndexes[0].id)" 2>/dev/null || echo "")

  if [ -z "$DEPLOYED_INDEX_ID" ]; then
      echo -e "${RED}Error: No deployed index found on endpoint ${INDEX_ENDPOINT}${NC}"
      echo ""
      echo "Ensure the index is deployed via Terraform, then try again."
      exit 1
  fi
fi

echo -e "  Backend: ${GREEN}Vertex AI Vector Search${NC}"
echo -e "  Endpoint: ${GREEN}${INDEX_ENDPOINT}${NC}"
echo -e "  Deployed Index ID: ${GREEN}${DEPLOYED_INDEX_ID}${NC}"
echo ""

# Check for GOOGLE_API_KEY
if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${YELLOW}Note: GOOGLE_API_KEY not set in environment${NC}"
    if [ -f ".env" ]; then
        echo -e "${YELLOW}Loading from .env file...${NC}"
        export $(grep -v '^#' .env | grep GOOGLE_API_KEY | xargs)
    fi
    
    if [ -z "$GOOGLE_API_KEY" ]; then
        echo -e "${RED}❌ Error: GOOGLE_API_KEY is required${NC}"
        echo ""
        echo "Please get your API key from: https://aistudio.google.com/app/apikey"
        echo "Then either:"
        echo "  1. Add it to .env file: GOOGLE_API_KEY=your-key-here"
        echo "  2. Export it: export GOOGLE_API_KEY=your-key-here"
        echo ""
        exit 1
    fi
fi

echo -e "${GREEN}✓ GOOGLE_API_KEY found${NC}"
echo ""

# Set environment variables for Vertex AI
export USE_VERTEX_RAG=true
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="$LOCATION"
export VERTEX_INDEX_ENDPOINT="$INDEX_ENDPOINT"
export VERTEX_DEPLOYED_INDEX_ID="$DEPLOYED_INDEX_ID"

# Use local JSON for profiles (not Firestore) during local testing
export USE_FIRESTORE=false
export USE_LOCAL_LLM=false

echo -e "${GREEN}Starting API server with Vertex AI...${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  USE_VERTEX_RAG:           ${GREEN}${USE_VERTEX_RAG}${NC}"
echo -e "  USE_FIRESTORE:            ${GREEN}${USE_FIRESTORE}${NC}"
echo -e "  GOOGLE_CLOUD_PROJECT:     ${GREEN}${GOOGLE_CLOUD_PROJECT}${NC}"
echo -e "  GOOGLE_CLOUD_LOCATION:    ${GREEN}${GOOGLE_CLOUD_LOCATION}${NC}"
echo -e "  VERTEX_INDEX_ENDPOINT:    ${GREEN}${VERTEX_INDEX_ENDPOINT}${NC}"
echo -e "  VERTEX_DEPLOYED_INDEX_ID: ${GREEN}${DEPLOYED_INDEX_ID}${NC}"
echo ""
echo -e "${YELLOW}Server will be available at: http://localhost:8000${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Ensure we run from the project root (directory containing api/main.py)
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Run the API server
uv run python api/main.py

