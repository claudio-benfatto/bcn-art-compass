"""
FastAPI application entry point.

Minimal FastAPI server with /chat endpoint for interacting with the
multi-agent cultural events recommender system.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.event_ranker import create_event_ranker
from agents.orchestrator import create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage
from observability import configure_logging, log_error, log_info, set_correlation_id
from rag.vector_store import VectorStore

# Global components
orchestrator = None
profile_agent = None
recommender_agent = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str
    correlation_id: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    """
    global orchestrator, profile_agent, recommender_agent

    # Startup
    configure_logging()
    log_info("application_started", service="bcn-art-compass-api")
    
    # Check if GOOGLE_API_KEY is available
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        log_error("google_api_key_missing", message="GOOGLE_API_KEY environment variable is not set")
    else:
        log_info("google_api_key_found", key_length=len(api_key))

    # Initialize components and agents externally
    try:
        # Initialize dependencies
        storage = MemoryStorage()
        
        # Try to initialize vector store (requires chromadb, not available in cloud)
        vector_store = None
        try:
            vector_store = VectorStore()  # Uses default settings
            log_info("vector_store_initialized")
        except (ImportError, Exception) as e:
            log_info("vector_store_unavailable", reason=str(e)[:100])
        
        event_ranker = create_event_ranker()

        log_info(
            "dependencies_initialized",
            has_storage=storage is not None,
            has_vector_store=vector_store is not None,
            has_event_ranker=event_ranker is not None,
        )

        # Create specialized agents
        profile_agent = create_profile_agent(
            storage=storage,
            model_name="gemini-2.5-flash-exp"
        )
        log_info("profile_agent_initialized")

        recommender_agent = create_recommender_agent(
            vector_store=vector_store,
            event_ranker=event_ranker,
            model_name="gemini-2.5-flash-exp"
        )
        log_info("recommender_agent_initialized")

        # Create orchestrator with pre-initialized agents and session persistence
        database_url = os.getenv("SESSION_DATABASE_URL", "sqlite:////tmp/sessions.db")
        orchestrator = create_orchestrator(
            profile_agent=profile_agent,
            recommender_agent=recommender_agent,
            model_name="gemini-2.5-flash-exp",
            database_url=database_url
        )
        log_info(
            "adk_orchestrator_initialized_with_external_agents",
            session_database=database_url
        )

    except Exception as e:
        log_error(
            "orchestrator_initialization_failed",
            error=str(e),
            error_type=type(e).__name__,
            traceback=True
        )
        log_info("api_will_run_with_limited_functionality")
        import traceback as tb
        tb.print_exc()  # Print to stderr for Cloud Run logs

    yield

    # Shutdown
    log_info("application_shutdown", service="bcn-art-compass-api")


# Create FastAPI app
app = FastAPI(
    title="BCN Art Compass API",
    description="Multi-agent cultural events recommender for Barcelona",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {"message": "BCN Art Compass API", "version": "0.1.0"}


@app.get("/healthz")
async def health_check() -> dict:
    """
    Liveness probe endpoint.

    Returns 200 if the application is running, regardless of dependencies.
    Used by container orchestrators to determine if the container should be restarted.
    """
    return {
        "status": "healthy",
        "service": "bcn-art-compass-api",
        "version": "0.1.0",
    }


@app.get("/readyz")
async def readiness_check() -> dict:
    """
    Readiness probe endpoint.

    Returns 200 if the application is ready to serve traffic.
    In cloud deployment, orchestrator may not be initialized if vector store
    is not available. Service can still handle basic queries via Gemini API.
    """
    components = {}
    
    if orchestrator is None:
        components["orchestrator"] = "not_initialized_will_use_gemini_fallback"
        components["rag"] = "disabled"
    else:
        components["orchestrator"] = "initialized"
        components["rag"] = "enabled"

    return {
        "status": "ready",
        "service": "bcn-art-compass-api",
        "version": "0.1.0",
        "components": components,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat endpoint for interacting with the cultural events recommender.

    Args:
        request: Chat request with user message and user_id

    Returns:
        ChatResponse with the agent's response and correlation_id
    """
    # Generate and set correlation ID for this request
    correlation_id = set_correlation_id()

    log_info(
        "chat_request_received",
        user_id=request.user_id,
        message_length=len(request.message),
    )

    try:
        # Use ADK orchestrator if available
        if orchestrator:
            response_text = await orchestrator.chat_async(request.user_id, request.message)
        else:
            response_text = (
                "The recommendation system is currently unavailable. "
                "Please ensure GOOGLE_API_KEY is set and try again."
            )

        log_info(
            "chat_response_generated",
            user_id=request.user_id,
            response_length=len(response_text),
        )

        return ChatResponse(
            response=response_text,
            correlation_id=correlation_id,
        )

    except Exception as e:
        log_error(
            "chat_request_error",
            user_id=request.user_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
