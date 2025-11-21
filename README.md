# BCN Art Compass 🎨

Multi-agent LLM system for recommending cultural events in Barcelona using Google ADK, RAG, and user memory.

## Project Status

**Milestone 0 - Day 0 (Setup): ✅ COMPLETE**
**Milestone 1 - Day 1-2 (Minimal RAG + Orchestrator): ✅ COMPLETE**
**Milestone 2 - Day 3-4 (Profile Memory): ✅ COMPLETE**
**Milestone 3 - Day 5-6 (Preference Extraction): ✅ COMPLETE**
**Milestone 4 - Day 7-8 (Clean Multi-Agent Workflow): ✅ COMPLETE**
**Milestone 5 - Day 9-10 (Local Demo Polishing + CLI + Docker): ✅ COMPLETE**

## Features

- ✅ FastAPI server with health endpoints (/healthz, /readyz)
- ✅ Structured logging with correlation IDs
- ✅ RAG search using ChromaDB with **free local embeddings** (zero API cost) or Google Gemini embeddings
- ✅ **3-agent architecture**: OrchestratorAgent, ProfileAgent, RecommenderAgent
- ✅ Multi-agent orchestrator with intent detection and conversation tracking
- ✅ Profile-based personalization with preference tracking
- ✅ **Natural language preference extraction** with multiple backends:
  - Google Gemini (cloud, requires API key)
  - Ollama/Llama (local LLM, free)
  - Rule-based fallback (simple keyword matching, zero dependencies)
- ✅ Profile-aware RAG scoring (boosts favorites, penalizes dislikes)
- ✅ **Interactive CLI** for conversational event discovery
- ✅ **Docker & Docker Compose** support for easy deployment
- ✅ 15 cultural events with venue data
- ✅ Event search & geocoding MCP tools
- ✅ Comprehensive test suite (**43 passing tests + Docker integration tests**)

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

### Choose Your LLM for Preference Extraction

The system supports three modes for extracting user preferences from natural language:

#### Option 1: Rule-Based (Default, Zero Cost, No Setup) 💡

Uses simple keyword matching to extract preferences. No API key or local model needed!

```bash
# Just run the CLI - it will auto-detect and use rule-based
uv run python cli.py
```

**Capabilities:**
- Detects likes: "I love contemporary art"
- Detects dislikes: "I don't like video art"
- Recognizes common art genres
- No external dependencies

#### Option 2: Local LLM via Ollama (Free, Better Quality) 🦙

Uses Llama3.2 running locally via Ollama for more accurate extraction.

```bash
# Install Ollama
brew install ollama  # macOS
# or download from https://ollama.com

# Pull Llama3.2 model
ollama pull llama3.2

# Start Ollama service
ollama serve

# Run CLI (will auto-detect Ollama)
uv run python cli.py

# Or explicitly force local LLM
USE_LOCAL_LLM=true uv run python cli.py
```

**Capabilities:**
- Understands complex preferences
- Extracts artist names
- Detects locations
- Handles mixed statements
- 100% free and private

#### Option 3: Google Gemini (Cloud, Best Quality) ☁️

Uses Google's Gemini-1.5-flash for the most accurate extraction.

```bash
# Set API key
export GOOGLE_API_KEY='your-api-key-here'

# Run CLI (will auto-detect API key)
uv run python cli.py

# Or explicitly force Gemini
USE_LOCAL_LLM=false uv run python cli.py
```

**Comparison:**

| Feature | Rule-Based | Ollama | Gemini |
|---------|------------|--------|--------|
| **Cost** | Free | Free | ~$0.00002/request |
| **Setup** | None | Install Ollama | API key |
| **Quality** | Basic | Good | Best |
| **Privacy** | Local | Local | Cloud |
| **Artists** | ❌ | ✅ | ✅ |
| **Locations** | ❌ | ✅ | ✅ |
| **Complex statements** | Limited | ✅ | ✅ |

**Recommendation:** Start with rule-based for instant setup, upgrade to Ollama for better quality while staying 100% free and local.

### Choose Your Embedding Option

The system supports both **free local embeddings** and **Google API embeddings** for RAG search:

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

### Running the Application

#### Option 1: Interactive CLI (Recommended for Local Use)

```bash
# Start the conversational CLI interface
uv run python cli.py
```

The CLI provides an interactive chat experience:
- Ask for event recommendations
- Update preferences in natural language
- Multi-turn conversations with context
- Graceful exit with 'quit' or Ctrl+C

#### Option 2: FastAPI Server

```bash
# Start the API server
uv run python main.py
```

The API will be available at `http://localhost:8000`.

#### Option 3: Docker

```bash
# Copy environment template
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

# Build and start with Docker Compose
docker-compose up -d

# Check health
curl http://localhost:8000/healthz

# Stop
docker-compose down
```

### Demos

```bash
# Demo 1: Basic RAG recommendations
PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Demo 2: Preference extraction and personalization
PYTHONPATH=$PWD uv run python scripts/demo_preferences.py
```

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

- `GET /` - Root endpoint with service info
- `GET /healthz` - Liveness probe (always returns 200)
- `GET /readyz` - Readiness probe (returns 200 when orchestrator is ready, 503 otherwise)
- `POST /chat` - Chat with the recommender

Example:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me contemporary art exhibitions", "user_id": "test_user"}'
```

### Health Endpoints

The service provides Kubernetes-compatible health checks:

- **`/healthz`** (Liveness): Returns 200 if the application is running. Container orchestrators use this to determine if the container should be restarted.
- **`/readyz`** (Readiness): Returns 200 if the application is ready to serve traffic, 503 otherwise. Checks that the orchestrator is initialized.

```bash
# Check liveness
curl http://localhost:8000/healthz

# Check readiness
curl http://localhost:8000/readyz
```

## Project Structure

```
bcn-art-compass/
├── agents/              # Multi-agent orchestration (M4)
│   ├── orchestrator.py # Orchestrator with conversation tracking
│   ├── profile_agent.py # Profile management & preference extraction
│   └── recommender_agent.py # Dedicated recommendation agent (M4)
├── api/                 # FastAPI application
│   └── main.py         # API endpoints with health checks (M5)
├── cli.py              # Interactive CLI interface (M5)
├── data/                # Event and venue data
│   ├── events.yaml     # 15 cultural events
│   └── venues.yaml     # 12 venues in Barcelona
├── memory/              # User profile storage (M2)
│   ├── models.py       # UserProfile Pydantic model
│   └── storage.py      # JSON-based persistence
├── observability/      # Structured logging
│   └── log_event.py   # Logging with correlation IDs
├── rag/                # RAG vector search
│   ├── models.py       # Pydantic models for events/venues
│   ├── embeddings.py   # Google Gemini embedding generation
│   ├── embeddings_local.py  # Local sentence-transformers (free!)
│   ├── vector_store.py # ChromaDB with profile-aware scoring
│   └── data_loader.py  # YAML data loading
├── scripts/            # Utility scripts
│   ├── init_vector_store.py  # Initialize ChromaDB
│   ├── demo_preferences.py   # Demo preference extraction
│   └── test_docker.sh  # Docker integration test runner (M5)
├── storage/            # Local data storage (generated)
│   ├── chromadb/       # ChromaDB persistence
│   └── profiles.json   # User profiles
├── tests/              # Test suite (43 + Docker tests)
│   ├── test_api.py    # API integration tests
│   ├── test_memory.py  # Memory storage tests
│   ├── test_preference_extraction.py  # Preference extraction
│   ├── test_integration_preferences.py  # End-to-end flow
│   ├── test_docker_integration.py  # Docker service tests (M5)
│   └── test_rag.py    # RAG component tests
├── tools/              # MCP tools
│   ├── event_search.py # Event search tool using RAG
│   └── geocoder.py    # Mock geocoding tool (M4)
├── Dockerfile         # Multi-stage Docker build (M5)
├── docker-compose.yml # Local Docker orchestration (M5)
├── .dockerignore      # Docker build exclusions (M5)
├── .env.example       # Environment template (M5)
├── main.py            # Application entry point
└── pyproject.toml     # Project configuration
```

## Key Features Explained

### 🤖 Multi-Agent Architecture (Milestone 4)

The system uses a clean 3-agent architecture with dedicated responsibilities:

**OrchestratorAgent** (Coordinator)
- Routes queries to appropriate agents
- Tracks conversation history (last 10 interactions per user)
- Manages multi-turn context
- Provides final user-facing responses

**ProfileAgent** (Memory Manager)
- Extracts preferences from natural language using Gemini LLM
- Manages user profile persistence (JSON storage)
- Tracks likes, dislikes, favorite artists, location

**RecommenderAgent** (RAG Specialist)
- Queries vector store with profile-aware scoring
- Ranks and formats event recommendations
- Delegates to VectorStore for semantic search

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

# Run Docker integration tests (requires Docker)
RUN_DOCKER_TESTS=true uv run pytest tests/test_docker_integration.py -v

# Or use the test script
./scripts/test_docker.sh
```

### Code Quality

```bash
# Run linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .
```

## Next Steps (Milestone 6+)

- Cloud Run deployment with Vertex AI Search
- Firestore backend for user profiles
- Enhanced ranking with geographic proximity
- Calendar integration MCP tool

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
