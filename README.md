# BCN Art Compass 🎨

Multi-agent LLM system for recommending cultural events in Barcelona using Google ADK, RAG, and user memory.

## Project Status

**Milestone 0 - Day 0 (Setup): ✅ COMPLETE**
**Milestone 1 - Day 1-2 (Minimal RAG + Orchestrator): ✅ COMPLETE**
**Milestone 2 - Day 3-4 (Profile Memory): ✅ COMPLETE**
**Milestone 3 - Day 5-6 (Preference Extraction): ✅ COMPLETE**

## Features

- ✅ FastAPI server with health endpoints
- ✅ Structured logging with correlation IDs
- ✅ RAG search using ChromaDB with **free local embeddings** (zero API cost) or Google Gemini embeddings
- ✅ Multi-agent orchestrator with intent detection
- ✅ Profile-based personalization with preference tracking
- ✅ **Natural language preference extraction using LLM**
- ✅ Profile-aware RAG scoring (boosts favorites, penalizes dislikes)
- ✅ 15 cultural events with venue data
- ✅ Event search MCP tool
- ✅ Comprehensive test suite (**43 passing tests**)

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- (Optional) Google API key for Gemini LLM

### Installation

```bash
# Install dependencies
uv sync

# Set Google API key (required for preference extraction)
export GOOGLE_API_KEY=your-api-key-here
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

### Demos

```bash
# Demo 1: Basic RAG recommendations
PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Demo 2: Preference extraction and personalization (Milestone 3)
PYTHONPATH=$PWD uv run python scripts/demo_preferences.py
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
│   ├── orchestrator.py # Orchestrator with intent detection (M3)
│   └── profile_agent.py # Profile management & preference extraction (M2, M3)
├── api/                 # FastAPI application
│   └── main.py         # API endpoints with orchestrator integration
├── data/                # Event and venue data
│   ├── events.yaml     # 15 cultural events
│   └── venues.yaml     # 12 venues in Barcelona
├── memory/              # User profile storage (Milestone 2)
│   ├── models.py       # UserProfile Pydantic model
│   └── storage.py      # JSON-based persistence
├── observability/      # Structured logging
│   └── log_event.py   # Logging utilities with correlation IDs
├── rag/                # RAG vector search
│   ├── models.py       # Pydantic models for events/venues
│   ├── embeddings.py   # Google Gemini embedding generation
│   ├── embeddings_local.py  # Local sentence-transformers embeddings (free!)
│   ├── vector_store.py # ChromaDB wrapper with profile-aware scoring
│   └── data_loader.py  # YAML data loading
├── scripts/            # Utility scripts
│   ├── init_vector_store.py  # Initialize ChromaDB with events
│   └── demo_preferences.py  # Demo preference extraction (M3)
├── storage/            # Local data storage (generated)
│   ├── chroma_db/      # ChromaDB persistence
│   └── user_profiles.json  # User profiles (M2)
├── tests/              # Test suite (43 passing)
│   ├── test_api.py    # API integration tests
│   ├── test_memory.py  # Memory storage tests (M2)
│   ├── test_preference_extraction.py  # Preference extraction tests (M3)
│   ├── test_integration_preferences.py  # End-to-end preference flow (M3)
│   ├── test_observability.py  # Observability unit tests
│   └── test_rag.py    # RAG component tests
├── tools/              # MCP tools
│   └── event_search.py # Event search tool using RAG
├── main.py            # Application entry point
└── pyproject.toml     # Project configuration
```

## Key Features Explained

### 🎯 Natural Language Preference Extraction (Milestone 3)

Users can express preferences in natural language, and the system extracts structured data:

```python
# User input: "I don't like video art"
# System extracts: {"disliked_genres": ["video art"]}

# User input: "I love contemporary sculpture and Picasso"
# System extracts: {
#   "favorite_genres": ["contemporary sculpture"],
#   "favorite_artists": ["Picasso"]
# }
```

**How it works:**
1. **Intent Detection**: Orchestrator detects preference expressions using keyword matching
2. **LLM Extraction**: ProfileAgent uses Gemini to parse natural language into structured JSON
3. **Profile Update**: Extracted preferences are merged with existing profile
4. **Persistence**: Profile is saved to `storage/user_profiles.json`
5. **Personalization**: Future queries use profile to adjust RAG scoring

**Example conversation:**
```
User: "Show me contemporary art exhibitions"
→ System returns recommendations

User: "I don't like video art"
→ Profile updated: disliked_genres = ["video art"]

User: "Find me interesting exhibitions"
→ System returns recommendations, video art events ranked lower
```

### 🔍 Profile-Aware RAG Scoring (Milestone 2)

The vector store applies preference-based adjustments to search results:

- **Favorite genres**: +0.2 score boost
- **Disliked genres**: -0.3 score penalty
- Results are re-ranked by adjusted scores

### 💾 User Profile Persistence (Milestone 2)

Each user has a profile stored in JSON:

```json
{
  "user_id": "user123",
  "favorite_genres": ["contemporary art", "sculpture"],
  "disliked_genres": ["video art"],
  "favorite_artists": ["Picasso", "Miró"],
  "location": null,
  "created_at": "2025-11-20T...",
  "updated_at": "2025-11-20T..."
}
```

## Development

### Running Tests

```bash
# Run all tests (43 passing)
uv run pytest -v

# Run specific test suites
uv run pytest tests/test_preference_extraction.py -v
uv run pytest tests/test_integration_preferences.py -v
uv run pytest tests/test_memory.py -v

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

## Next Steps (Milestone 4)

- Implement multi-agent workflow with ADK
- Add more sophisticated agent collaboration
- Enhance recommendation logic
- Add calendar integration MCP tool

## Tech Stack

- **Framework**: Google ADK (Agent Development Kit)
- **LLM**: Google Gemini (gemini-1.5-flash)
- **Embeddings**: 
  - Local: sentence-transformers (all-MiniLM-L6-v2) - Free
  - Cloud: Google text-embedding-004 - ~$0.00001/1K chars
- **Vector DB**: ChromaDB (local), Vertex AI Search (cloud)
- **API**: FastAPI
- **Observability**: structlog
- **Testing**: pytest
- **Deployment**: Cloud Run (future)

## License

MIT
