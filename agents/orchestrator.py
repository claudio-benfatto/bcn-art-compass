"""
Orchestrator Agent with Profile Integration.

Routes user queries to the appropriate handler (RAG search or fallback).
In Milestone 2, integrates ProfileAgent to load user preferences.
"""

from typing import TYPE_CHECKING, Optional

from agents.profile_agent import ProfileAgent
from observability import log_agent_routing, log_info
from rag.vector_store import VectorStore

if TYPE_CHECKING:
    from memory.models import UserProfile


class OrchestratorAgent:
    """
    Orchestrator for routing user queries with profile awareness.

    Responsibilities:
    - Load user profile before processing queries
    - Route queries to RAG with profile context
    - Return fallback for non-recommendation queries
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        profile_agent: Optional[ProfileAgent] = None,
        use_local_embeddings: Optional[bool] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            vector_store: VectorStore instance for RAG queries. If None, creates a new one
            profile_agent: ProfileAgent instance. If None, creates a new one
            use_local_embeddings: Explicit choice. If None, auto-detects from USE_LOCAL_EMBEDDINGS env var
        """
        if vector_store:
            self.vector_store = vector_store
        else:
            # Let VectorStore handle auto-detection via environment variables
            self.vector_store = VectorStore(use_local_embeddings=use_local_embeddings)

        self.profile_agent = profile_agent or ProfileAgent()

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

        # Keywords that indicate preference updates
        self.preference_keywords = {
            "like": ["like", "love", "enjoy", "prefer", "favorite", "fan of"],
            "dislike": ["don't like", "dislike", "hate", "not interested in", "not a fan"],
        }

        log_info("orchestrator_initialized", with_profile_agent=True)

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

    def _detect_intent(self, query: str) -> str:
        """
        Detect user intent from query.

        Args:
            query: User query text

        Returns:
            Intent type: 'preference_update', 'recommendation', or 'general'
        """
        query_lower = query.lower()

        # Check for preference expressions
        for keyword in self.preference_keywords["like"]:
            if keyword in query_lower:
                return "preference_update"
        for keyword in self.preference_keywords["dislike"]:
            if keyword in query_lower:
                return "preference_update"

        # Check for recommendation requests
        if self._should_use_rag(query):
            return "recommendation"

        # Default to general
        return "general"

    async def process_query(self, query: str, user_id: str = "default_user") -> str:
        """
        Process a user query and return a response.

        In Milestone 2, loads user profile and passes to RAG.
        In Milestone 3, detects preference updates and extracts them.

        Args:
            query: User's natural language query
            user_id: User identifier

        Returns:
            Response text
        """
        log_info("orchestrator_processing_query", user_id=user_id, query_length=len(query))

        # Detect intent
        intent = self._detect_intent(query)
        log_info("intent_detected", user_id=user_id, intent=intent)

        # Handle preference updates
        if intent == "preference_update":
            profile = await self.profile_agent.extract_preferences(user_id, query)
            log_info(
                "preference_extracted_and_saved",
                user_id=user_id,
                favorite_genres=len(profile.favorite_genres),
                disliked_genres=len(profile.disliked_genres),
                favorite_artists=len(profile.favorite_artists),
            )
            return (
                "Got it! I've updated your preferences. "
                f"You now have {len(profile.favorite_genres)} favorite genre(s) "
                f"and {len(profile.disliked_genres)} disliked genre(s). "
                "Your future recommendations will reflect these preferences!"
            )

        # Load user profile for other queries
        profile = self.profile_agent.load_profile(user_id)
        # Load user profile for other queries
        profile = self.profile_agent.load_profile(user_id)
        log_info(
            "profile_loaded_for_query",
            user_id=user_id,
            has_preferences=len(profile.favorite_genres) > 0 or len(profile.favorite_artists) > 0,
        )

        # Decide routing
        use_rag = intent == "recommendation"

        log_agent_routing(
            agent_name="orchestrator",
            decision="use_rag" if use_rag else "fallback",
            user_query=query[:100],  # Log first 100 chars
        )

        if use_rag:
            return self._handle_recommendation_query(query, profile)
        else:
            return self._handle_fallback(query)

    def _handle_recommendation_query(self, query: str, profile: "UserProfile") -> str:
        """
        Handle recommendation queries using RAG with profile context.

        Args:
            query: User query
            profile: User profile with preferences

        Returns:
            Formatted response with event recommendations
        """
        log_info("handling_recommendation_query", query=query[:100])

        # Query the vector store with profile
        results = self.vector_store.query(query, k=5, profile=profile)

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
