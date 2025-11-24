# Scripts

Utility scripts for BCN Art Compass deployment, data processing, and Vertex AI management.

## Directory Structure

### `deployment/`
Scripts for deploying the application to Cloud Run.

- **`deploy.sh`** - Basic Cloud Run deployment
- **`deploy_with_vertex.sh`** - Cloud Run deployment with Vertex AI configuration
- **`test_docker.sh`** - Docker build and test validation

Usage:
```bash
./scripts/deployment/deploy.sh
./scripts/deployment/deploy_with_vertex.sh
```

### `data/`
Scripts for building and managing vector store indexes.

- **`init_vector_store.py`** - Initialize local ChromaDB vector store
- **`build_chromadb_index.py`** - Build ChromaDB index from events.yaml
- **`prepare_vertex_data.py`** - Generate embeddings for Vertex AI Vector Search

Usage:
```bash
uv run python scripts/data/init_vector_store.py
uv run python scripts/data/build_chromadb_index.py
uv run python scripts/data/prepare_vertex_data.py
```

### `vertex/`
Scripts for managing Vertex AI Vector Search infrastructure.

- **`setup_vertex_ai.sh`** - Initial Vertex AI index and endpoint setup
- **`update_vertex_index.sh`** - Update Vertex AI index with new events
- **`check_vertex_status.sh`** - Check Vertex AI index and endpoint status
- **`cli_vertex.sh`** - Run CLI with Vertex AI configuration

Usage:
```bash
./scripts/vertex/setup_vertex_ai.sh
./scripts/vertex/update_vertex_index.sh
./scripts/vertex/check_vertex_status.sh
```

## Common Workflows

### Initial Setup (Local Development)
```bash
# 1. Build local vector store
uv run python scripts/data/init_vector_store.py

# 2. Run the application
uv run python cli.py
```

### Initial Setup (Cloud with Vertex AI)
```bash
# 1. Setup Vertex AI infrastructure
./scripts/vertex/setup_vertex_ai.sh

# 2. Deploy to Cloud Run
./scripts/deployment/deploy_with_vertex.sh
```

### Updating Event Data
```bash
# Edit data/events.yaml, then:

# For local:
uv run python scripts/data/build_chromadb_index.py

# For cloud:
./scripts/vertex/update_vertex_index.sh
```

## Environment Variables

Required for cloud scripts:
- `GOOGLE_CLOUD_PROJECT` - Your GCP project ID
- `GOOGLE_CLOUD_LOCATION` - GCP region (default: europe-southwest1)
- `GOOGLE_API_KEY` - Gemini API key for embeddings
