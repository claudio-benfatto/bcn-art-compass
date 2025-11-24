#!/bin/bash
# Setup Google API Key secret in Secret Manager
# Run this ONCE before deploying to Cloud Run

set -e

PROJECT_ID="bcn-art-compass"
SECRET_NAME="google-api-key"

echo "=========================================="
echo "Setup Google API Key for Cloud Run"
echo "=========================================="
echo ""

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo "❌ Not authenticated. Run: gcloud auth login"
    exit 1
fi

# Set project
gcloud config set project "$PROJECT_ID"

echo "This script will create a secret in Google Secret Manager"
echo "to store your Google API key (for Gemini)."
echo ""
echo "You can get your API key from:"
echo "  https://aistudio.google.com/app/apikey"
echo ""

# Check if secret already exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo "⚠️  Secret '$SECRET_NAME' already exists."
    echo ""
    read -p "Do you want to update it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    
    # Update existing secret
    read -s -p "Enter your Google API key: " API_KEY
    echo ""
    
    if [ -z "$API_KEY" ]; then
        echo "❌ API key cannot be empty"
        exit 1
    fi
    
    echo -n "$API_KEY" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID"
    
    echo "✅ Secret updated successfully"
else
    # Create new secret
    read -s -p "Enter your Google API key: " API_KEY
    echo ""
    
    if [ -z "$API_KEY" ]; then
        echo "❌ API key cannot be empty"
        exit 1
    fi
    
    echo -n "$API_KEY" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID"
    
    echo "✅ Secret created successfully"
fi

echo ""
echo "Secret '$SECRET_NAME' is ready for Cloud Run deployment."
echo "You can now run: ./scripts/deploy-to-cloud-run.sh"
