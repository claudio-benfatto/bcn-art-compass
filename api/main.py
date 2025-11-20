"""
FastAPI application entry point.

Minimal FastAPI server with /chat endpoint for interacting with the
multi-agent cultural events recommender system.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from observability import configure_logging, log_info, set_correlation_id


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
    # Startup
    configure_logging()
    log_info("application_started", service="bcn-art-compass-api")

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
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/readyz")
async def readiness_check() -> dict:
    """Readiness check endpoint."""
    return {"status": "ready"}


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
        # TODO: In Milestone 1, this will call the orchestrator agent
        # For now, just echo back a placeholder response
        response_text = f"Echo (placeholder): {request.message}"

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
