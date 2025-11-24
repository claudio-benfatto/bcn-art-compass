# AI Art Guide – Copilot Instructions

## How I’d like you to work

I am building a multi-agent LLM system using the Google ADK (Agent Development Kit) with deployment on Cloud Run. The system uses:

- RAG (Vertex AI Search / vector DB) for cultural events & venues
- User memory (Firestore or local JSON) for long-term preferences
- Multi-agent orchestration (2–3 agents inside ADK)
- MCP tools for external data fetching

## A 2-week MVP scope

- Ability to run both locally and in Cloud Run

When you generate code or suggestions, please:
- Prefer Python
- Use Google ADK patterns (agents, tools, pipelines)
- Suggest Cloud-friendly, stateless designs
- Provide lightweight examples that run locally as well
- Use clean, modular file structures
- Avoid over-engineering—everything must be MVP friendly
- Include comments explaining why something is done

## My project goals

This project is an MVP for a cultural events recommender:

- A user interacts in natural language
- System retrieves events via RAG
- User preferences and dislikes are stored and updated across conversations
- Multi-turn context must refine recommendations
- Use 2–3 LLM agents with clear roles
- Use MCP tools for optional external sources
- Deploy backend on Cloud Run
- Keep everything runnable locally using local embeddings/vector DB

When helping me, focus on:

- Clean architectural boundaries
- RAG integration patterns
- Multi-agent collaboration ideas
- Memory storage strategies
- Cloud Run deployment templates
- Examples runnable with uv run main.py

## Code conventions

Please follow:

- Python 3.12
- Use uv for the env + package management
- Use Google ADK idioms:
  - Agent
  - RunContext
  - @tool for MCP-style tools
- Use pydantic models for structured data
- Async when possible
- Show minimal examples but correct architecture
- Avoid:
  - Excessive boilerplate
  - Overly complex agent routing logic
  - External dependencies unless strictly needed

## Tools & Framework Preferences

When generating code, prefer the following stack:

- RAG
  - Local: ChromaDB
  - Cloud: Vertex AI Search or Vertex Vector Search

- Embeddings: text-embedding-005 or local sentence-transformers

- Agents
  - google-generativeai (Gemini models)
  - Google ADK agents with multistep workflows

- Memory
  - Long-term: Firestore (cloud) / local JSON
  - Short-term: ADK context object

- External Tools (MCP)
  - Provide examples of MCP tool definitions
  - Simple: event fetcher, HTTP fetcher, location resolver

## Preferred multi-agent structure

When designing or generating code, follow this 3-agent architecture:

### 1. Orchestrator Agent
- Routes tasks & decides whether RAG or user memory is needed
- Provides final user-facing answer

### 2. RAG Search Agent
- Queries the vector DB / Vertex AI Search
- Returns structured event results

### 3. User Profile Agent
- Reads/writes long-term memory
- Tracks likes, dislikes, preferences

If only two agents are needed, merge #1 and #3.

## Deployment Preferences

When generating deployment files:

- Use Cloud Run (fully managed)
- Use a Dockerfile slim image
- Expose a minimal FastAPI or Flask endpoint used by the ADK agent
- Provide local fallback config (.env.local)
- Use Google service accounts via workload identity when possible

Include:
- cloudbuild.yaml (simple)
- Example gcloud run deploy command

Avoid:
- Kubernetes configs
- Heavy CI/CD pipelines for MVP

## Documentation Style

When generating documentation, format it as:

- GitHub-style markdown
- With diagrams using Mermaid when useful
- With clear folder structure trees
- With tasks broken into 2-week MVP milestones

## Examples I want from you

When I ask for help, generate content like:

- A complete agents/ folder with orchestrator + rag_agent + profile_agent
- Sample RAG ingestion pipeline
- Memory update examples
- Sample Cloud Run service
- MCP tool definitions
- Testable local version using ChromaDB
- A short user journey example
- README sections I can paste to GitHub

## Things to avoid

Please avoid:

- Overly abstract theory
- Multi-cloud setups
- Enterprise-grade IAM setups
- Transforming this into a giant multi-agent ecosystem
- Opaque “magic” code without explanations
- Examples that cannot run both local and cloud

## Architecture & Data Flow
```
events.yaml → Pydantic validation → precompute_embeddings.py → generated/vertex_embeddings.jsonl 
→ ChromaDB vector store → EventRetriever → retrieve_events tool → ADK framework
```

**Key Principle**: All filtering (tags, dates, geo) happens in the vector store layer, not post-processing. This ensures accurate top_k results and efficient queries.

## Directory structure
```
project/
  agents/
    orchestrator.py
    profile_agent.py
    recommender_agent.py

  tools/
    event_search_mcp.py
    geocoder_mcp.py
    calendar_mcp.py (optional)

  memory/
    user_profiles.json     # local memory

  rag/
    index/                 # local vector DB
    build_index.py         # embedding + ingestion
    query_index.py

  data/
    events.yaml            # dataset of events
    venues.yaml            # dataset of venues

  main.py                  # entry point (starts orchestrator agent)
```

### Overview

This MVP implements a multi-agent LLM system that recommends cultural events (art exhibitions, museums, performances) based on:

- User natural-language queries
- User long-term profile & preferences
- RAG search over a vector database of events & venues
- Multi-turn conversation context
- External tools via MCP (event search, geocoding, etc.)

The MVP is limited to 2–3 agents, must run locally and in the cloud, and must be deliverable within two weeks.

## Architecture Diagram

```plaintext
User
  ↓
Orchestrator Agent  
       │
       ├──► Profile Agent (long-term memory: preferences, location)
       │
       └──► Recommender Agent (RAG + scoring)
                  │
                  └── MCP Tools (event_search, geocoder, calendar)

````

## Agent Roles
### 1. Orchestrator Agent
The only agent the user interacts with.

#### Responsibilities

- Maintains conversation flow
- Determines which agent to call
- Merges responses into a coherent answer
- Manages short-term session context
- Routes MCP tool calls if needed
- Detects preference updates and forwards them to Profile Agent

#### Why it exists
To showcase multi-agent orchestration without over-engineering.

### 2. Profile Agent
Long-term memory and preference manager.

#### Responsibilities

- Maintain the user's profile:
  - location
  - liked genres
  - disliked genres
  - favorite artists
- Parse natural-language statements about preferences
- Persist profile information for future sessions

#### Storage

Local: JSON file or SQLite
Cloud: Firestore / Cloud Storage

#### Why it exists
Shows memory, personalization, and statefulness across sessions.

### 3. Recommender Agent (RAG Agent)

Event/venue retrieval, ranking, and recommendation.

#### Responsibilities
- Query vector DB using embeddings
- Filter + score based on:
  - user preferences
  - similarity to query
  - geographic distance
- Call MCP tools (event_search, geocoder)
- Return ranked recommendations

#### Why it exists
To showcase RAG, semantic search, and tool-enhanced reasoning.

## MCP Tools Used in MVP

| Tool | Purpose |
|------|---------|
| `event_search` | Queries RAG vector DB for events/venues |
| `geocoder` | Converts addresses/locations to coordinates |
| `calendar` (optional) | Demo ability to add events to calendar |

## Memory Model

### Short-Term Memory
- ADK conversation state
- Lives only within a session

### Long-Term Memory
- Stored by Profile Agent:
````
{
  "user_id": "123",
  "location": "Barcelona",
  "favorite_genres": ["contemporary art", "sculpture"],
  "disliked_genres": ["video art"],
  "favorite_artists": ["Picasso"],
  "preferred_distance_km": 20
}
````

## Testability

For every new component you help me design (agents, MCP tools, RAG pipeline, memory manager, server entrypoints, utilities), always generate:

- Unit tests
- Integration tests

Tests must:
- Use pytest
- Run locally using uv run -m pytest
- Include fixtures for mock vector DB, mock memory storage, sample embeddings, fake user profile, and mocking MCP external calls
- Include integration tests that execute the full pipeline (orchestrator → rag_agent → profile_agent)

All generated code should be testable offline without external services.

## Observability

Add lightweight observability to all components:

- Use Python logging with JSON or structured logs
- Log agent routing decisions, RAG queries, memory updates, and MCP tool calls
- Emit logs to stdout (Cloud Run compatible)
- Include a small helper like observability.log_event() used throughout the code
- Include correlation IDs for each user session
- Keep it minimal and MVP-friendly.

## Agent Quality Evaluation (Optional)

- Do not include this by default, but when asked:
- Generate evaluation tests for agent trajectories
- Provide judge-model evaluation scaffolding
- Test routing correctness, memory updates, and RAG relevance
- Support reproducible evaluation runs using uv run

This is optional and post-MVP unless explicitly requested.