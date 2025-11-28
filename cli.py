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
from agents.orchestrator import create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage
from rag.vector_store import VectorStore
from rag.embeddings_local import LocalEmbeddingGenerator
from agents.event_ranker import create_event_ranker

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
