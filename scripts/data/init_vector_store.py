"""
Script to initialize the RAG vector store with events data.

Run this script to load events and venues into ChromaDB before starting the API.
Uses local sentence-transformer embeddings (no API key required).

Usage:
    uv run scripts/init_vector_store.py
"""

from observability import configure_logging, log_info
from rag.data_loader import load_events_with_venues
from rag.vector_store import VectorStore


def initialize_vector_store():
    """Initialize the vector store with events data."""
    configure_logging()
    
    log_info("initializing_vector_store", embedding_type="local")

    try:
        # Load data
        log_info("loading_events_and_venues")
        events_with_venues = load_events_with_venues()
        log_info("loaded_data", count=len(events_with_venues))

        # Initialize vector store with local embeddings
        log_info("creating_vector_store")
        vector_store = VectorStore()

        # Clear existing data (optional - comment out if you want to keep existing data)
        if vector_store.count() > 0:
            log_info("clearing_existing_data", current_count=vector_store.count())
            vector_store.clear()

        # Add documents
        log_info("adding_documents_to_vector_store")
        vector_store.add_documents(events_with_venues)

        final_count = vector_store.count()
        log_info("vector_store_initialized", document_count=final_count)

        print(f"\n✅ Vector store initialized successfully with {final_count} events")
        print("💡 Using local embeddings (sentence-transformers)")
        print()
        return True

    except Exception as e:
        log_info("initialization_failed", error=str(e), level="error")
        print(f"\n❌ Error initializing vector store: {e}\n")
        return False


if __name__ == "__main__":
    success = initialize_vector_store()
    exit(0 if success else 1)
