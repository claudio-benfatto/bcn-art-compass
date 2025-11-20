# Two-Week MVP Plan — Vertical Slices With Working Checkpoints

This plan is optimized for fast feedback, local demo at every milestone, and copilot-aligned constraints:

- Uses uv for env + deps
- Every checkpoint includes:
  - Agents
  - RAG
  - Memory
  - Tools
  - Tests
  - Observability
- Cloud deployment added only after local is stable
- Multi-agent complexity grows over time

## Milestone 0 — Day 0 (Setup)
### Goals
- Skeleton environment
- Folder structure
- Boilerplate

### Tasks

- Init repo:
```
uv init
uv add google-generativeai chromadb pydantic fastapi pytest structlog
```
- Create base folder structure:
```
agents/
rag/
memory/
tools/
api/
tests/
observability/
storage/
```
- Add observability/log_event.py with structured logging
- Add basic pytest config
- Add a minimal FastAPI skeleton /chat endpoint

### Result:
- A runnable empty FastAPI server + tests working.

## Milestone 1 — Day 1–2
First Vertical Slice: Minimal RAG + Minimal Orchestrator + No Memory

### Goal
- A working first end-to-end pipeline: User query → Orchestrator → RAG → Result

### Tasks
#### RAG
- Create data/events.yaml and data/venues.yaml (15 dummy events)
- Add simple embedding generation with Gemini text-embedding-005
- Implement ChromaDB wrapper:
  - add_documents()
  - query(text, k)

#### Agent
- Implement minimal OrchestratorAgent
  - if query contains “recommend”, call RAG, else fallback

#### Tool
- Implement MCP event_search calling local RAG

#### Tests

- Add unit tests for RAG wrapper
- Integration test: /chat → orchestrator → rag → response

✔️ Working Checkpoint 1

You can now:
- Ask for something → get events from RAG.
- Works locally, logs structured.

## Milestone 2 — Day 3–4
Profile Memory + Profile Agent + Retrieval in Recommendation Flow

### Goal

- Introduce memory, but stay in a minimal slice.

- User query → Orchestrator  
                ↳ Profile Agent (load profile)  
                ↳ RAG  
                → Response

### Tasks
#### Memory
- Implement JSON-based memory storage
  - load_profile(user_id)
  - save_profile(user_id)

#### Profile Agent
- Minimal version:
  - Loads profile
  - Can store static defaults (e.g., fav genres)

#### Orchestrator
- Load profile before running RAG
- Pass profile to RAG agent

#### Tests

- Unit test for JSON memory
- Integration: profile load influences ranking (e.g., favor sculpture)

✅ **Milestone 2 COMPLETE**
- ✅ JSON memory storage with MemoryStorage class
- ✅ UserProfile Pydantic model with preferences tracking
- ✅ ProfileAgent for loading/saving profiles
- ✅ Orchestrator integration with profile loading
- ✅ Profile-aware RAG scoring (+0.2 boost, -0.3 penalty)
- ✅ 9 memory unit tests (28 total tests passing)

Working local demo with profile-based recommendations.

---

## Milestone 3 — Day 5–6 ✅ COMPLETE
Preference Extraction + Updating Memory

### Goal
Enable user to express likes/dislikes and have them persist.

Example:
“I don’t like video art.”
User → Orchestrator → Profile Agent (extract+update) → saved memory

### Tasks
#### Profile Agent
- ✅ Implement preference extraction NLP with LLM (Gemini)
- ✅ Update profile:
  - ✅ likes (favorite_genres)
  - ✅ dislikes (disliked_genres)
  - ✅ artists (favorite_artists)
  - ✅ genres

#### Orchestrator
- ✅ Add intent detection:
  - ✅ preference_update vs recommendation vs general
  - ✅ Keyword-based detection
- ✅ Route to ProfileAgent.extract_preferences() for preference updates
- ✅ Persist profile before returning response

#### Tests
- ✅ NLP extraction tests with mocked LLM (11 tests)
- ✅ Integration tests: preference → profile → influences next rec (4 tests)
- ✅ Test coverage:
  - Simple likes/dislikes
  - Multiple preferences in one statement
  - Artist mentions, location extraction
  - Error handling, JSON parsing edge cases
  - Markdown cleanup, profile persistence
  - End-to-end preference flow

### Deliverables

✅ **Milestone 3 COMPLETE**
- ✅ ProfileAgent.extract_preferences() using Gemini LLM
- ✅ Intent detection in Orchestrator (_detect_intent method)
- ✅ Preference extraction with JSON parsing and error handling
- ✅ 15 new tests (11 unit + 4 integration)
- ✅ **43 total tests passing**
- ✅ Demo script (scripts/demo_preferences.py)
- ✅ Updated documentation (README.md)

**Key Features:**
- Users express preferences in natural language
- LLM extracts structured preferences from free text
- Preferences persist across sessions in JSON storage
- Future recommendations personalized based on profile
- Both likes and dislikes tracked and applied to RAG scoring

Locally you can refine results with natural language preferences.

---

## Milestone 4 — Day 7–8
Clean Multi-Agent Workflow

### Goal
Add the real multi-agent logic with orchestrator routing.

Agents now:
- Orchestrator Agent
- Profile Agent
- Recommender Agent

Flow:

1. Orchestrator decides intent
2. Updates or loads memory
3. Recommender agent queries RAG
4. Returns structured recommendations

### Tasks

#### Recommender Agent
- Rank function incorporating profile:
  - score += profile.likes
  - score -= profile.dislikes

#### Orchestrator Agent

- Add conversation context tracking (last user query, last results)

#### Tools
- Add mock geocoder MCP tool (returns sample lat/lon)

#### Tests
- Full integration test: user → update memory → get refined recs
- Test routing logic inside orchestrator

✔️ Working Checkpoint 4

A fully functional multi-agent demo.

## Milestone 5 — Day 9–10
Local Demo Polishing + CLI + Docker

### Goal
Make local demo production-espresso.

#### Tasks
- Add CLI interface (text-based chat)
- Add Dockerfile using uv:
- RUN uv sync --frozen
- Add health endpoints /healthz /readyz
- Add more logs with correlation IDs

#### Tests

- Integration test against local Dockerized service

✔️ Working Checkpoint 5

Polished local demo + docker deployable service.

## Milestone 6 — Day 11–12

Cloud Run Transition Layer


### Goal
Introduce cloud-switchable components.

### Tasks
#### Vector DB
- Add Vertex AI Vector Search wrapper
- Switch using env var USE_VERTEX_RAG=true

#### Memory
- Add Firestore backend with identical API to JSON memory

#### Deployment
- Add deployment script for Cloud Run

#### Tests
- Mock Firestore tests
- Smoke test script hitting cloud endpoint

✔️ Working Checkpoint 6

You can deploy a minimal version to Cloud Run.

## Milestone 7 — Day 13–14
Final MVP Hardening

### Tasks

- Improve ranking heuristics using location proximity (mock geocoder OK)
- Better fallback logic (“no results found”)
- Add sample evaluation harness (optional, not default)
- Produce documentation for usage & architecture

✔️ Final MVP

Fully functioning multi-agent RAG recommender
- Preference learning
- Local + Cloud Run compatibility
- Tests
- Observability
- CLI + API
- Extensible to production

## 🌟 Summary of Working Checkpoints

| Day | Checkpoint | Works Locally? | Includes… |
|-----|------------|----------------|-----------|
| 0 | Setup | ✔ | env + scaffolding |
| 2 | CP1 | ✔ | basic RAG + orchestrator |
| 4 | CP2 | ✔ | profile-aware RAG |
| 6 | CP3 | ✔ | preference learning |
| 8 | CP4 | ✔ | multi-agent flow |
| 10 | CP5 | ✔ | polished local demo |
| 12 | CP6 | ✔ | Cloud Run support |
| 14 | Final | ✔ | full MVP |
