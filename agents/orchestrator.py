"""
Minimal Orchestrator Agent.

Routes user queries to the appropriate handler (RAG search or fallback).
This is a simplified version for Milestone 1 - no memory, just basic routing.
"""

from typing import Optional

from observability import log_agent_routing, log_info
from rag.vector_store import VectorStore


class OrchestratorAgent:
    """
    Minimal orchestrator for routing user queries.

    In Milestone 1, this simply decides:
    - If query contains recommendation keywords → call RAG
    - Otherwise → return fallback message
    """

    def __init__(self, vector_store: Optional[VectorStore] = None, use_local_embeddings: Optional[bool] = None):
        """
        Initialize the orchestrator.

        Args:
            vector_store: VectorStore instance for RAG queries. If None, creates a new one
            use_local_embeddings: Explicit choice. If None, auto-detects from USE_LOCAL_EMBEDDINGS env var
        """
        if vector_store:
            self.vector_store = vector_store
        else:
            # Let VectorStore handle auto-detection via environment variables
            self.vector_store = VectorStore(use_local_embeddings=use_local_embeddings)

        # Keywords that trigger RAG search
        self.recommendation_keywords = [
            "recommend",
            "show",
            "find",
            "search",
            "looking for",
            "interested in",
            "want to see",
            "what",
            "where",
            "exhibition",
            "event",
            "art",
            "museum",
            "gallery",
        ]

        log_info("orchestrator_initialized")

    def _should_use_rag(self, query: str) -> bool:
        """
        Determine if query should trigger RAG search.

        Args:
            query: User query text

        Returns:
            True if query should use RAG, False otherwise
        """
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.recommendation_keywords)

    def process_query(self, query: str, user_id: str = "default_user") -> str:
        """
        Process a user query and return a response.

        Args:
            query: User's natural language query
            user_id: User identifier (not used in Milestone 1)

        Returns:
            Response text
        """
        log_info("orchestrator_processing_query", user_id=user_id, query_length=len(query))

        # Decide routing
        use_rag = self._should_use_rag(query)

        log_agent_routing(
            agent_name="orchestrator",
            decision="use_rag" if use_rag else "fallback",
            user_query=query[:100],  # Log first 100 chars
        )

        if use_rag:
            return self._handle_recommendation_query(query)
        else:
            return self._handle_fallback(query)

    def _handle_recommendation_query(self, query: str) -> str:
        """
        Handle recommendation queries using RAG.

        Args:
            query: User query

        Returns:
            Formatted response with event recommendations
        """
        log_info("handling_recommendation_query", query=query[:100])

        # Query the vector store
        results = self.vector_store.query(query, k=5)

        if not results:
            return "I couldn't find any events matching your query. Could you try rephrasing?"

        # Format response
        response_lines = [f"I found {len(results)} events that might interest you:\n"]

        for i, result in enumerate(results, 1):
            response_lines.append(f"{i}. **{result.title}** at {result.venue_name}")
            response_lines.append(f"   {result.description[:150]}...")
            response_lines.append(f"   📅 {result.start_date} to {result.end_date}")
            response_lines.append(f"   🎨 {', '.join(result.genres[:3])}")
            response_lines.append(f"   💰 {result.cost_range}")
            response_lines.append(f"   🔗 {result.url}\n")

        log_info("recommendation_response_generated", num_results=len(results))
        return "\n".join(response_lines)

    def _handle_fallback(self, query: str) -> str:
        """
        Handle queries that don't trigger RAG.

        Args:
            query: User query

        Returns:
            Fallback response
        """
        log_info("handling_fallback_query", query=query[:100])

        return (
            "I'm here to help you discover cultural events in Barcelona! "
            "Try asking me to:\n"
            "- Recommend contemporary art exhibitions\n"
            "- Find sculpture events\n"
            "- Show me what's happening this month\n"
            "- Search for free events\n\n"
            "What would you like to explore?"
        )
