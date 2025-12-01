#!/usr/bin/env python3
"""
Interactive CLI for BCN Art Compass.

Provides a text-based conversational interface for discovering cultural events
in Barcelona. Supports multi-turn conversations with preference learning.

Automatically detects environment and uses either:
- Local ChromaDB + sentence-transformers (default)
- Vertex AI Vector Search + Gemini embeddings (if USE_VERTEX_RAG=true)
"""

import os
import sys
import asyncio
import io

from agents.orchestrator import create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage
from rag.vector_store import VectorStore
from rag.embeddings_local import LocalEmbeddingGenerator
from agents.event_ranker import create_event_ranker
from observability import configure_logging


class _FilteredStream(io.TextIOBase):
    """Filter out known noisy deprecation lines from underlying libraries."""

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def write(self, s: str) -> int:  # type: ignore[override]
        # Suppress specific noisy lines from underlying libraries but pass
        # everything else through unchanged.
        noisy_fragments = [
            "Deprecated. Please migrate to the async method.",
            "EventsCompactionConfig: This feature is experimental",
            "App name mismatch detected. The runner is configured with app name",
        ]
        if any(fragment in s for fragment in noisy_fragments):
            return len(s)
        return self._wrapped.write(s)

    def flush(self) -> None:  # type: ignore[override]
        return self._wrapped.flush()


# Install filtered stdout/stderr as early as possible in the CLI process
sys.stdout = _FilteredStream(sys.stdout)  # type: ignore[assignment]
sys.stderr = _FilteredStream(sys.stderr)  # type: ignore[assignment]

# Configure structured logging for CLI: default to ERROR to avoid noisy internals.
# Set BCN_LOG_LEVEL=INFO or DEBUG to see more detail when debugging.
configure_logging(log_level=os.getenv("BCN_LOG_LEVEL", "ERROR"))

# Check for required API key
if not os.getenv("GOOGLE_API_KEY"):
    print("=" * 70)
    print("ERROR: GOOGLE_API_KEY environment variable is not set")
    print("=" * 70)
    print()
    print("The BCN Art Compass CLI requires a Google AI API key to function.")
    print()
    print("To get an API key:")
    print("  1. Visit: https://aistudio.google.com/app/apikey")
    print("  2. Create or copy your API key")
    print("  3. Set it in your environment:")
    print()
    print("     export GOOGLE_API_KEY='your-api-key-here'")
    print()
    print("Then run the CLI again: uv run cli.py")
    print("=" * 70)
    sys.exit(1)

# Initialize dependencies
storage = MemoryStorage()
embedding_generator = LocalEmbeddingGenerator()
vector_store = VectorStore(
    collection_name="events",
    embedding_generator=embedding_generator,
    persist_directory="storage/chroma_db"
)
event_ranker = create_event_ranker()

# Create agents
profile_agent = create_profile_agent(storage=storage)
recommender_agent = create_recommender_agent(
    vector_store=vector_store,
    event_ranker=event_ranker
)
orchestrator = create_orchestrator(profile_agent, recommender_agent)


def main():
    print("Welcome to BCN Art Compass CLI! Type your query below.")
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
            try:
                response = asyncio.run(orchestrator.chat_async("cli_user", user_input))
                print(f"Compass: {response}")
            except Exception as e:
                print(f"[ERROR] Exception during orchestrator execution: {type(e).__name__}: {e}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break



if __name__ == "__main__":
    main()
