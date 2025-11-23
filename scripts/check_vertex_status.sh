#!/bin/bash
#
# Check Vertex AI Vector Search index and endpoint status
#
# Usage: ./scripts/check_vertex_status.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-bcn-art-compass}
REGION=${2:-europe-southwest1}

echo "================================================"
echo "Vertex AI Status Check"
echo "================================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check indexes
echo "Indexes:"
gcloud ai indexes list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="table(displayName,name,metadata.state)"

echo ""

# Check endpoints
echo "Index Endpoints:"
gcloud ai index-endpoints list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="table(displayName,name)"

echo ""

# If index exists, show deployed indexes
INDEX_NAME=$(gcloud ai indexes list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --filter="displayName:bcn-art-compass-index" \
    --format="value(name)" 2>/dev/null)

if [ -n "$INDEX_NAME" ]; then
    echo "Index Details:"
    gcloud ai indexes describe "$INDEX_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID"
    echo ""
fi

# If endpoint exists, show details
ENDPOINT_NAME=$(gcloud ai index-endpoints list \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --filter="displayName:bcn-art-compass-endpoint" \
    --format="value(name)" 2>/dev/null)

if [ -n "$ENDPOINT_NAME" ]; then
    echo "Endpoint Details:"
    gcloud ai index-endpoints describe "$ENDPOINT_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID"
fi
