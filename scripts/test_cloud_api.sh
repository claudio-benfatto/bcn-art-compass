#!/bin/bash
# Test script for BCN Art Compass Cloud Run deployment

set -e

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe bcn-art-compass \
  --region=europe-southwest1 \
  --format='value(status.url)')

echo "Testing BCN Art Compass API at: $SERVICE_URL"
echo ""

# Test 1: Root endpoint
echo "✓ Testing root endpoint..."
curl -s "$SERVICE_URL/" | jq .
echo ""

# Test 2: Health check
echo "✓ Testing health endpoint..."
curl -s "$SERVICE_URL/healthz"
echo ""

# Test 3: Readiness check
echo "✓ Testing readiness endpoint..."
curl -s "$SERVICE_URL/readyz"
echo ""

# Test 4: Chat endpoint - simple greeting
echo "✓ Testing chat endpoint (greeting)..."
curl -s -X POST "$SERVICE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_'$(date +%s)'",
    "message": "Hello!"
  }' | jq .
echo ""

# Test 5: Chat endpoint - preference extraction
echo "✓ Testing chat endpoint (preferences)..."
curl -s -X POST "$SERVICE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_preferences",
    "message": "I love contemporary art and sculpture, but I dont like video art"
  }' | jq .
echo ""

# Test 6: Chat endpoint - location
echo "✓ Testing chat endpoint (location)..."
curl -s -X POST "$SERVICE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_location",
    "message": "I am in Barcelona, near Sagrada Familia"
  }' | jq .
echo ""

# Test 7: Chat endpoint - recommendations
echo "✓ Testing chat endpoint (recommendations)..."
curl -s -X POST "$SERVICE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_recs",
    "message": "What art exhibitions can you recommend this weekend?"
  }' | jq .
echo ""

echo "✅ All tests completed!"
