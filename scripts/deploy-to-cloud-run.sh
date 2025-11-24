#!/bin/bash
# Deploy BCN Art Compass to Cloud Run
# This script automates the deployment process with proper secret management

set -e  # Exit on error

PROJECT_ID="bcn-art-compass"
REGION="europe-southwest1"
SERVICE_NAME="bcn-art-compass"
SECRET_NAME="google-api-key"

echo "=========================================="
echo "BCN Art Compass - Cloud Run Deployment"
echo "=========================================="
echo ""

# Check if user is authenticated
echo "→ Checking GCloud authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo "❌ Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi
echo "✓ Authenticated"
echo ""

# Set the project
echo "→ Setting project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"
echo ""

# Check if secret exists
echo "→ Checking if API key secret exists..."
if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo ""
    echo "❌ Secret '$SECRET_NAME' not found in Secret Manager"
    echo ""
    echo "Please create the secret with your Google API key (Gemini):"
    echo ""
    echo "  echo -n 'YOUR_ACTUAL_API_KEY' | gcloud secrets create $SECRET_NAME \\"
    echo "    --data-file=- \\"
    echo "    --project=$PROJECT_ID"
    echo ""
    echo "After creating the secret, run this script again."
    exit 1
fi
echo "✓ Secret '$SECRET_NAME' exists"
echo ""

# Grant Cloud Run access to the secret
echo "→ Granting Cloud Run access to the secret..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --member="serviceAccount:$CLOUD_RUN_SA" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" \
    --quiet

echo "✓ Service account has access to secret"
echo ""

# Generate image tag
IMAGE_TAG=$(date +%Y%m%d-%H%M%S)

echo "→ Starting Cloud Build deployment..."
echo "   Image tag: $IMAGE_TAG"
echo "   Region: $REGION"
echo ""

# Trigger Cloud Build
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions="_DEPLOY_REGION=$REGION,_IMAGE_TAG=$IMAGE_TAG" \
    --project="$PROJECT_ID"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Deployment successful!"
    echo "=========================================="
    echo ""
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)")
    
    echo "Service URL: $SERVICE_URL"
    echo ""
    echo "Test endpoints:"
    echo "  Health: $SERVICE_URL/healthz"
    echo "  Ready:  $SERVICE_URL/ready"
    echo "  Chat:   $SERVICE_URL/chat"
    echo ""
else
    echo ""
    echo "❌ Deployment failed. Check the logs above for details."
    exit 1
fi
