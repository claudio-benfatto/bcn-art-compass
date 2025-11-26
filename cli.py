#!/usr/bin/env python3
"""
Interactive CLI for BCN Art Compass.

Provides a text-based conversational interface for discovering cultural events
in Barcelona. Supports multi-turn conversations with preference learning.

Automatically detects environment and uses either:
- Local ChromaDB + sentence-transformers (default)
- Vertex AI Vector Search + Gemini embeddings (if USE_VERTEX_RAG=true)
"""

import asyncio
import sys
import uuid

import config
from agents.event_ranker import create_event_ranker
from agents.orchestrator import create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage
from observability import log_event


def print_banner():
    """Print welcome banner."""
    app_config = config.get_config()
    rag_mode = "Vertex AI" if app_config.use_vertex_rag else "Local ChromaDB"
    
    print("\n" + "=" * 60)
    print("🎨 BCN Art Compass - Your Cultural Event Guide")
    print("=" * 60)
    print(f"\n📍 Environment: {app_config.environment}")
    print(f"🔍 RAG Backend: {rag_mode}")
    print("\nWelcome! I can help you discover art exhibitions, museums,")
    print("and cultural events in Barcelona.")
    print("\nCommands:")
    print("  - Ask for recommendations: 'What art exhibitions are on?'")
    print("  - Update preferences: 'I love contemporary art'")
    print("  - Exit: 'quit', 'exit', or Ctrl+C")
    print("=" * 60 + "\n")


def print_response(response: str):
    """Format and print agent response."""
    print("\n🤖 Assistant:")
    print("-" * 60)
    print(response)
    print("-" * 60 + "\n")


def initialize_system():
    """Initialize all components."""
    log_event("cli_initialization_started")

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Initialize RAG components based on config
    app_config = config.get_config()
    
    if app_config.use_vertex_rag:
        print("⏳ Connecting to Vertex AI Vector Search...")
        print(f"   Project: {app_config.project_id}")
        print(f"   Location: {app_config.location}")
        
        from rag.vector_store_vertex import VertexVectorStore
        vector_store = VertexVectorStore.from_env()
        print(f"✅ Vertex AI connected with {len(vector_store.events_map)} events")
    else:
        print("⏳ Loading local embedding model (first run may take a minute)...")
        from rag.embeddings_local import LocalEmbeddingGenerator
        from rag.vector_store import VectorStore
        
        embedding_generator = LocalEmbeddingGenerator()
        print("⏳ Initializing local vector store...")
        vector_store = VectorStore(
            collection_name="events",
            embedding_generator=embedding_generator,
            persist_directory="storage/chroma_db"
        )

        # Check if vector store has data
        try:
            test_results = vector_store.collection.count()
            if test_results == 0:
                print("\n⚠️  Warning: Vector store is empty!")
                print("Please run: PYTHONPATH=$PWD uv run python scripts/init_vector_store.py")
                print("Then restart the CLI.\n")
        except Exception:
            pass  # Continue anyway

    # Initialize storage and event ranker
    storage = MemoryStorage()
    event_ranker = create_event_ranker()

    # Create specialized agents externally
    profile_agent = create_profile_agent(
        storage=storage,
        model_name="gemini-2.5-flash-exp"
    )
    
    recommender_agent = create_recommender_agent(
        vector_store=vector_store,
        event_ranker=event_ranker,
        model_name="gemini-2.5-flash-exp"
    )

    # Create orchestrator with pre-initialized agents
    orchestrator = create_orchestrator(
        profile_agent=profile_agent,
        recommender_agent=recommender_agent,
        model_name="gemini-2.5-flash-exp"
    )

    log_event("cli_initialization_complete", session_id=session_id)
    print("✅ System ready!\n")

    return orchestrator, session_id


def get_user_id() -> str:
    """Get or create user ID."""
    print("👤 Please enter your user ID (or press Enter for default 'user-1'):")
    user_id = input("> ").strip()

    if not user_id:
        user_id = "user-1"

    log_event("user_identified", user_id=user_id)
    print(f"\n✓ Using user ID: {user_id}\n")

    return user_id


def main():
    """Main CLI loop."""
    asyncio.run(async_main())


async def async_main():
    """Async main CLI loop."""
    try:
        print_banner()

        # Initialize system
        orchestrator, session_id = initialize_system()

        # Get user ID
        user_id = get_user_id()

        # Main conversation loop
        turn = 0
        while True:
            try:
                # Get user input
                print("💬 You:")
                user_input = input("> ").strip()

                # Check for exit commands
                if user_input.lower() in ["quit", "exit", "bye", "goodbye"]:
                    print("\n👋 Goodbye! Enjoy exploring Barcelona's art scene!")
                    log_event("cli_session_ended", session_id=session_id, turns=turn)
                    break

                # Skip empty input
                if not user_input:
                    continue

                turn += 1

                # Log user query
                log_event(
                    "cli_user_query",
                    session_id=session_id,
                    user_id=user_id,
                    turn=turn,
                    query_length=len(user_input)
                )

                # Process query (async)
                response = await orchestrator.chat_async(user_id=user_id, message=user_input)

                # Display response
                print_response(response)

                # Log response
                log_event(
                    "cli_response_delivered",
                    session_id=session_id,
                    user_id=user_id,
                    turn=turn,
                    response_length=len(response)
                )

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                log_event("cli_interrupted", session_id=session_id, turns=turn)
                break
            except Exception as e:
                log_event(
                    "cli_error",
                    session_id=session_id,
                    error=str(e),
                    turn=turn
                )
                print(f"\n❌ Error: {e}")
                print("Please try again or type 'quit' to exit.\n")

    except Exception as e:
        log_event("cli_fatal_error", error=str(e))
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
