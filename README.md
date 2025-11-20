# BCN Art Compass 🎨

Multi-agent LLM system for recommending cultural events in Barcelona using Google ADK, RAG, and user memory.

## Project Status

**Milestone 0 - Day 0 (Setup): ✅ COMPLETE**
**Milestone 1 - Day 1-2 (Minimal RAG + Orchestrator): ✅ COMPLETE**

## Features

- ✅ FastAPI server with health endpoints
- ✅ Structured logging with correlation IDs
- ✅ RAG search using ChromaDB with **free local embeddings** (zero API cost) or Google Gemini embeddings
- ✅ Minimal orchestrator agent for query routing
- ✅ 15 cultural events with venue data
- ✅ Event search MCP tool
- ✅ Comprehensive test suite (19 passing tests)

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Install dependencies
uv sync
```

### Choose Your Embedding Option

The system supports both **free local embeddings** and **Google API embeddings**. You can control which one to use:

#### Auto-Detection (Default)
- No API key → Uses **local embeddings** (free)
- API key present → Uses **Google API embeddings** (paid)

#### Explicit Control via Flag

Use `USE_LOCAL_EMBEDDINGS` environment variable to explicitly choose:

```bash
# Force local embeddings (even if API key is set)
export USE_LOCAL_EMBEDDINGS=true
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Force Google API embeddings (requires API key)
export GOOGLE_API_KEY='your-api-key-here'
export USE_LOCAL_EMBEDDINGS=false
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
```

#### Option 1: Free Local Embeddings (Default, Zero Cost) 💡

Uses `sentence-transformers` (all-MiniLM-L6-v2 model, 384 dimensions).
**No API key needed, completely free!**

```bash
# Initialize the vector store
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Run the demo
PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Start the API server
uv run python main.py
```

#### Option 2: Google API Embeddings (Better Quality, ~$0.00001 per 1K chars)

Uses Google's `text-embedding-004` model (768 dimensions).

```bash
# Set your Google API key
export GOOGLE_API_KEY='your-api-key-here'

# Initialize the vector store (will auto-use Google API)
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Or explicitly force it
export USE_LOCAL_EMBEDDINGS=false
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Run the demo
PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Start the API server
uv run python main.py
```

### Testing

```bash
# Run all tests
uv run pytest -v

# Run tests including optional embedding tests (requires GOOGLE_API_KEY)
uv run pytest -v --run-embedding-tests
```

The API will be available at `http://localhost:8000`.

### Embedding Options Comparison

| Feature | Local Embeddings | Google API Embeddings |
|---------|-----------------|----------------------|
| **Cost** | 💰 Free | ~$0.00001 per 1K chars |
| **API Key Required** | ❌ No | ✅ Yes (GOOGLE_API_KEY) |
| **Dimensions** | 384 | 768 |
| **Model** | all-MiniLM-L6-v2 | text-embedding-004 |
| **Download Size** | ~91 MB (one-time) | None |
| **Quality** | Good for demos/dev | Production-grade |
| **Speed** | Fast (local) | Depends on network |

**Recommendation**: Start with local embeddings for development, switch to Google API for production if you need higher quality.

### API Endpoints

- `GET /` - Root endpoint
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `POST /chat` - Chat with the recommender

Example:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me contemporary art exhibitions", "user_id": "test_user"}'
```

## Project Structure

```
bcn-art-compass/
├── agents/              # Multi-agent orchestration
│   └── orchestrator.py # Minimal orchestrator (routes to RAG or fallback)
├── api/                 # FastAPI application
│   └── main.py         # API endpoints with orchestrator integration
├── data/                # Event and venue data
│   ├── events.yaml     # 15 cultural events
│   └── venues.yaml     # 12 venues in Barcelona
├── memory/             # User profile storage (Milestone 2)
├── observability/      # Structured logging
│   └── log_event.py   # Logging utilities with correlation IDs
├── rag/                # RAG vector search
│   ├── models.py       # Pydantic models for events/venues
│   ├── embeddings.py   # Google Gemini embedding generation
│   ├── embeddings_local.py  # Local sentence-transformers embeddings (free!)
│   ├── vector_store.py # ChromaDB wrapper with auto-detect embedding option
│   └── data_loader.py  # YAML data loading
├── scripts/            # Utility scripts
│   └── init_vector_store.py  # Initialize ChromaDB with events
├── storage/            # Local data storage (generated)
│   └── chroma_db/      # ChromaDB persistence
├── tests/              # Test suite
│   ├── test_api.py    # API integration tests
│   ├── test_observability.py  # Observability unit tests
│   └── test_rag.py    # RAG component tests
├── tools/              # MCP tools
│   └── event_search.py # Event search tool using RAG
├── main.py            # Application entry point
└── pyproject.toml     # Project configuration
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest -v

# Run only unit tests
uv run pytest -v -m unit

# Run only integration tests
uv run pytest -v -m integration
```

### Code Quality

```bash
# Run linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .
```

## Next Steps (Milestone 2)

- Implement JSON-based memory storage
- Add Profile Agent for user preferences
- Load profile before running RAG
- Pass user profile to recommendation scoring

## Tech Stack

- **Framework**: Google ADK (Agent Development Kit)
- **LLM**: Google Gemini models
- **Embeddings**: text-embedding-005
- **Vector DB**: ChromaDB (local), Vertex AI Search (cloud)
- **API**: FastAPI
- **Observability**: structlog
- **Testing**: pytest
- **Deployment**: Cloud Run (future)

## License

MIT
