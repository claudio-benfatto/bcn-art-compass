# BCN Art Compass 🎨

Multi-agent LLM system for recommending cultural events in Barcelona using Google ADK, RAG, and user memory.

## Project Status

**Milestone 0 - Day 0 (Setup): ✅ COMPLETE**

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest -v

# Start the API server
uv run python main.py
```

The API will be available at `http://localhost:8000`.

### API Endpoints

- `GET /` - Root endpoint
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `POST /chat` - Chat with the recommender (placeholder echo for now)

Example:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me contemporary art exhibitions", "user_id": "test_user"}'
```

## Project Structure

```
bcn-art-compass/
├── agents/              # Multi-agent orchestration (empty for now)
├── api/                 # FastAPI application
│   └── main.py         # API endpoints
├── memory/             # User profile storage (empty for now)
├── observability/      # Structured logging
│   └── log_event.py   # Logging utilities
├── rag/                # RAG vector search (empty for now)
├── storage/            # Local data storage (empty for now)
├── tests/              # Test suite
│   ├── test_api.py    # API integration tests
│   └── test_observability.py  # Observability unit tests
├── tools/              # MCP tools (empty for now)
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

## Next Steps (Milestone 1)

- Create `data/events.yaml` and `data/venues.yaml`
- Implement ChromaDB wrapper for RAG
- Build minimal OrchestratorAgent
- Add MCP `event_search` tool

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
