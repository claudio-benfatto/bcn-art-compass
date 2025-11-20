"""
Demo script showing the RAG pipeline in action.

This demonstrates the full pipeline without needing to start the API server.

Usage:
    # Use free local embeddings (default, no API key needed):
    uv run scripts/demo_rag.py

    # Use Google API embeddings (requires GOOGLE_API_KEY):
    export GOOGLE_API_KEY=your_key
    uv run scripts/demo_rag.py
"""

import os

from observability import configure_logging, log_info
from rag.data_loader import load_events_with_venues
from rag.vector_store import VectorStore


def demo_rag_pipeline():
    """Demonstrate the RAG pipeline with example queries."""
    configure_logging()
    
    # Determine which embeddings to use
    # Priority: USE_LOCAL_EMBEDDINGS flag > presence of GOOGLE_API_KEY
    env_flag = os.getenv("USE_LOCAL_EMBEDDINGS", "").lower()
    if env_flag in ("true", "1", "yes"):
        use_local = True
        embedding_type = "local (forced by flag)"
    elif env_flag in ("false", "0", "no"):
        use_local = False
        embedding_type = "Google API (forced by flag)"
    else:
        use_local = "GOOGLE_API_KEY" not in os.environ
        embedding_type = "local (no API key)" if use_local else "Google API (auto-detected)"
    
    log_info("starting_rag_demo", embedding_type=embedding_type)

    print("\n" + "=" * 60)
    print("BCN Art Compass - RAG Pipeline Demo")
    print("=" * 60)
    if use_local:
        print("💡 Using free local embeddings (sentence-transformers)")
    else:
        print("💡 Using Google API embeddings (text-embedding-004)")
    print()

    # Initialize vector store
    print("📦 Initializing vector store...")
    vector_store = VectorStore(use_local_embeddings=use_local)

    # Check if data is loaded
    if vector_store.count() == 0:
        print("⚠️  Vector store is empty. Loading data...")
        events_with_venues = load_events_with_venues()
        vector_store.add_documents(events_with_venues)
        print(f"✅ Loaded {vector_store.count()} events into vector store\n")
    else:
        print(f"✅ Vector store ready with {vector_store.count()} events\n")

    # Example queries
    queries = [
        "Show me contemporary sculpture exhibitions",
        "I want to see Picasso art",
        "Find outdoor art activities",
        "What experimental art is available?",
        "Recommend family-friendly events",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n{'─' * 60}")
        print(f"Query {i}: {query}")
        print("─" * 60 + "\n")

        results = vector_store.query(query, k=3)

        if results:
            print(f"Found {len(results)} results:\n")
            for j, result in enumerate(results, 1):
                print(f"{j}. {result.title}")
                print(f"   📍 {result.venue_name}")
                print(f"   🎨 {', '.join(result.genres[:2])}")
                print(f"   📅 {result.start_date} to {result.end_date}")
                print(f"   💰 {result.cost_range}")
                print(f"   📊 Relevance: {result.score:.3f}")
                print()
        else:
            print("No results found.\n")

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    demo_rag_pipeline()
