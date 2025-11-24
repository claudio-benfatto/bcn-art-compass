# Cloud Run Deployment Guide

## Overview

This guide walks you through deploying BCN Art Compass to Google Cloud Run with proper secret management for your Google API key.

## Prerequisites

1. **Google Cloud Project**: `bcn-art-compass`
2. **gcloud CLI**: Installed and authenticated
3. **Google API Key**: For Gemini models (get one at https://aistudio.google.com/app/apikey)
4. **Required APIs enabled**:
   - Cloud Run API
   - Cloud Build API
   - Secret Manager API (enabled automatically by scripts)
   - Firestore API

## Deployment Process

### Step 1: Setup API Key Secret (One-time)

Run this script to securely store your Google API key in Secret Manager:

```bash
./scripts/setup-api-key-secret.sh
```

This will:
- Create a secret named `google-api-key` in Secret Manager
- Prompt you to enter your API key (hidden input)
- Store it securely for Cloud Run to access

**Note**: You only need to run this once. To update the key later, run it again and choose to update.

### Step 2: Deploy to Cloud Run

Run the deployment script:

```bash
./scripts/deploy-to-cloud-run.sh
```

This will:
1. Verify authentication and project setup
2. Check that the API key secret exists
3. Grant Cloud Run service account access to the secret
4. Trigger a Cloud Build deployment
5. Deploy the container to Cloud Run with:
   - 512Mi memory
   - 1 CPU
   - Auto-scaling (0-1 instances)
   - Firestore integration enabled
   - Your API key injected as `GOOGLE_API_KEY` environment variable

### Step 3: Test the Deployment

Once deployed, the script will output the service URL. Test the endpoints:

```bash
# Health check
curl https://YOUR-SERVICE-URL/healthz

# Ready check
curl https://YOUR-SERVICE-URL/ready

# Chat endpoint (POST)
curl -X POST https://YOUR-SERVICE-URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "message": "What exhibitions are happening in Barcelona?"
  }'
```

## Architecture

### Cloud Build Pipeline

The deployment uses `cloudbuild.yaml` with these steps:

1. **Build Docker Image**: Multi-stage build with Python 3.13 + uv
2. **Push to GCR**: Store in Google Container Registry
3. **Deploy to Cloud Run**: Deploy with secrets and environment variables

### Environment Variables

Set automatically by the deployment:

- `GOOGLE_API_KEY`: From Secret Manager (for Gemini)
- `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
- `GOOGLE_CLOUD_LOCATION`: Deployment region (europe-southwest1)
- `USE_FIRESTORE`: `true` (enables Firestore for user profiles)
- `USE_VERTEX_RAG`: `false` (uses local ChromaDB)
- `USE_LOCAL_LLM`: `false` (uses Gemini)
- `PORT`: `8080` (default Cloud Run port)

### Service Configuration

- **Region**: europe-southwest1 (Madrid, Spain)
- **Memory**: 512Mi
- **CPU**: 1
- **Timeout**: 60 seconds
- **Max instances**: 1 (to control costs)
- **Min instances**: 0 (scale to zero when idle)
- **Concurrency**: 80 requests per instance
- **Authentication**: Public (no auth required)

## Troubleshooting

### Container Failed to Start

**Symptom**: Deployment fails with "container failed to start and listen on port"

**Common causes**:
1. Missing `GOOGLE_API_KEY` secret
2. Application crashes during initialization
3. Timeout (container takes too long to start)

**Solution**:
1. Check Cloud Run logs:
   ```bash
   gcloud run services logs read bcn-art-compass --region=europe-southwest1
   ```
2. Verify secret exists:
   ```bash
   gcloud secrets describe google-api-key --project=bcn-art-compass
   ```
3. Check service account permissions:
   ```bash
   gcloud secrets get-iam-policy google-api-key --project=bcn-art-compass
   ```

### Secret Not Found

**Symptom**: Deployment script says "Secret 'google-api-key' not found"

**Solution**: Run `./scripts/setup-api-key-secret.sh` first

### Permission Denied

**Symptom**: Cloud Run can't access the secret

**Solution**: The deployment script automatically grants access, but you can manually fix it:

```bash
PROJECT_NUMBER=$(gcloud projects describe bcn-art-compass --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding google-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=bcn-art-compass
```

### Build Timeout

**Symptom**: Cloud Build times out during image build

**Solution**: The default timeout is 900s (15 min). This should be sufficient. If it still times out:
- Check network connectivity
- Try again (sometimes GCP has temporary issues)

## Manual Deployment (Alternative)

If you prefer to deploy manually without the scripts:

### 1. Create the secret

```bash
echo -n 'YOUR_API_KEY' | gcloud secrets create google-api-key \
  --data-file=- \
  --project=bcn-art-compass
```

### 2. Grant access

```bash
PROJECT_NUMBER=$(gcloud projects describe bcn-art-compass --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding google-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=bcn-art-compass
```

### 3. Deploy

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions="_DEPLOY_REGION=europe-southwest1,_IMAGE_TAG=$(date +%Y%m%d-%H%M%S)" \
  --project=bcn-art-compass
```

## Monitoring

### View Logs

```bash
# Real-time logs
gcloud run services logs tail bcn-art-compass --region=europe-southwest1

# Recent logs
gcloud run services logs read bcn-art-compass --region=europe-southwest1 --limit=100
```

### Check Service Status

```bash
gcloud run services describe bcn-art-compass --region=europe-southwest1
```

### View in Cloud Console

- **Cloud Run**: https://console.cloud.google.com/run?project=bcn-art-compass
- **Cloud Build**: https://console.cloud.google.com/cloud-build/builds?project=bcn-art-compass
- **Secret Manager**: https://console.cloud.google.com/security/secret-manager?project=bcn-art-compass
- **Logs**: https://console.cloud.google.com/logs?project=bcn-art-compass

## Updating the Deployment

To update the deployment with new code:

1. Commit your changes
2. Run `./scripts/deploy-to-cloud-run.sh`
3. A new Docker image will be built and deployed

The deployment script automatically:
- Generates a new image tag (timestamp)
- Builds the Docker image
- Pushes to GCR
- Deploys to Cloud Run
- Maintains the previous version (for rollback if needed)

## Rollback

To rollback to a previous version:

```bash
# List revisions
gcloud run revisions list --service=bcn-art-compass --region=europe-southwest1

# Route traffic to a specific revision
gcloud run services update-traffic bcn-art-compass \
  --to-revisions=REVISION_NAME=100 \
  --region=europe-southwest1
```

## Cost Optimization

The current configuration is optimized for MVP costs:

- **Scale to zero**: No cost when idle
- **512Mi memory**: Minimum viable for Python apps
- **1 CPU**: Sufficient for MVP traffic
- **Max 1 instance**: Prevents runaway costs
- **CPU throttling**: Reduces cost when idle
- **E2 machine type**: 30% cheaper than N1

**Estimated cost**: ~$0.10-0.50/day with light usage, $0 when completely idle

## Security

- **API keys**: Stored in Secret Manager (encrypted at rest)
- **No API key in code**: Never commit keys to Git
- **IAM permissions**: Only Cloud Run service account has access
- **Public endpoint**: Currently unauthenticated (add auth for production)

## Next Steps

For production:

1. **Add authentication**: Use Cloud Run IAM or Firebase Auth
2. **Custom domain**: Map your own domain
3. **Monitoring**: Set up Cloud Monitoring alerts
4. **Increase resources**: Scale memory/CPU based on traffic
5. **CDN**: Add Cloud CDN for static assets
6. **Multiple regions**: Deploy to multiple regions for HA
