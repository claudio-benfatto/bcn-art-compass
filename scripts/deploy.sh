#!/bin/bash
# Deploy BCN Art Compass to Google Cloud Run
# Usage: ./scripts/deploy.sh [PROJECT_ID] [REGION]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 BCN Art Compass - Cloud Run Deployment${NC}"
echo ""

# Configuration
PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT}}"
REGION="${2:-us-central1}"
SERVICE_NAME="bcn-art-compass"

# Validate project ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID not set${NC}"
    echo "Usage: ./scripts/deploy.sh [PROJECT_ID] [REGION]"
    echo "Or set GOOGLE_CLOUD_PROJECT environment variable"
    exit 1
fi

echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service: $SERVICE_NAME"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: gcloud CLI not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
echo -e "${YELLOW}Checking authentication...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${RED}❌ Not authenticated${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi
echo -e "${GREEN}✓ Authenticated${NC}"

# Set project
echo -e "${YELLOW}Setting project...${NC}"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    firestore.googleapis.com \
    --project="$PROJECT_ID"
echo -e "${GREEN}✓ APIs enabled${NC}"

# Build using Cloud Build
echo -e "${YELLOW}Building with Cloud Build...${NC}"
gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_DEPLOY_REGION="$REGION" \
    --project="$PROJECT_ID"

# Get service URL
echo -e "${YELLOW}Getting service URL...${NC}"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(status.url)")

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo -e "${GREEN}Service URL:${NC} $SERVICE_URL"
echo ""
echo -e "${YELLOW}Test the service:${NC}"
echo "  Health check: curl $SERVICE_URL/healthz"
echo "  Readiness: curl $SERVICE_URL/readyz"
echo "  Chat: curl -X POST $SERVICE_URL/chat -H 'Content-Type: application/json' -d '{\"message\": \"Hello\", \"user_id\": \"test\"}'"
echo ""
echo -e "${YELLOW}View logs:${NC}"
echo "  gcloud run services logs read $SERVICE_NAME --region=$REGION --project=$PROJECT_ID"
echo ""
echo -e "${YELLOW}Manage service:${NC}"
echo "  gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID"
