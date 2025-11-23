"""
FastAPI application entry point.

Minimal FastAPI server with /chat endpoint for interacting with the
multi-agent cultural events recommender system.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.orchestrator import OrchestratorAgent
from observability import configure_logging, log_error, log_info, set_correlation_id

# Global orchestrator instance
orchestrator: Optional[OrchestratorAgent] = None


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
    global orchestrator

    # Startup
    configure_logging()
    log_info("application_started", service="bcn-art-compass-api")

    # Initialize orchestrator (will create vector store if needed)
    try:
        orchestrator = OrchestratorAgent()
        log_info("orchestrator_initialized")
    except Exception as e:
        log_error("orchestrator_initialization_failed", error=str(e))
        log_error("api_will_run_without_rag")

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
        # Use orchestrator if available, otherwise fallback
        if orchestrator:
            response_text = await orchestrator.process_query(request.message, request.user_id)
        else:
            response_text = (
                "The recommendation system is currently unavailable. "
                "Please ensure GOOGLE_API_KEY is set and the vector store is initialized."
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
        log_info(
            "chat_request_error",
            user_id=request.user_id,
            error=str(e),
            level="error",
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
