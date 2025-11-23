"""
Orchestrator Agent - Multi-agent workflow coordinator.

Routes user queries to appropriate agents:
- ProfileAgent: User preferences and memory
- RecommenderAgent: Event recommendations with RAG

Milestone 2: Added ProfileAgent integration
Milestone 3: Added preference extraction with intent detection
Milestone 4: Added RecommenderAgent and conversation context
"""

from typing import TYPE_CHECKING, Optional

from agents.profile_agent import ProfileAgent
from agents.recommender_agent import RecommenderAgent
from observability import log_agent_routing, log_info

if TYPE_CHECKING:
    from memory.models import UserProfile


def _create_vector_store():
    """Create the appropriate vector store based on config."""
    try:
        import config
        log_info("config_imported_successfully")
        
        should_use_vertex = config.should_use_vertex_rag()
        log_info("config_check_complete", use_vertex=should_use_vertex)
        
        if should_use_vertex:
            # Use Vertex AI Vector Search
            from rag.vector_store_vertex import VertexVectorStore
            log_info("creating_vertex_vector_store")
            store = VertexVectorStore.from_env()
            log_info("vertex_vector_store_created_successfully")
            return store
        else:
            # Use local ChromaDB
            from rag.vector_store import VectorStore
            log_info("creating_chroma_vector_store")
            return VectorStore()
    except Exception as e:
        log_info("vector_store_creation_failed", error=str(e), error_type=type(e).__name__)
        import traceback
        traceback.print_exc()
        # Fallback to ChromaDB
        from rag.vector_store import VectorStore
        log_info("falling_back_to_chroma")
        return VectorStore()


class OrchestratorAgent:
    """
    Orchestrator for multi-agent workflow coordination.

    Responsibilities (Milestone 4):
    - Detect user intent (preference_update, recommendation, general)
    - Load and update user profiles via ProfileAgent
    - Delegate recommendations to RecommenderAgent
    - Track conversation context for multi-turn interactions
    - Route queries to appropriate agents
    """

    def __init__(
        self,
        recommender_agent: Optional[RecommenderAgent] = None,
        profile_agent: Optional[ProfileAgent] = None,
        use_local_embeddings: Optional[bool] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            recommender_agent: RecommenderAgent instance. If None, creates a new one
            profile_agent: ProfileAgent instance. If None, creates a new one
            use_local_embeddings: Deprecated, use config.py instead
        """
        # Create vector store based on config
        vector_store = _create_vector_store()
        
        self.recommender_agent = recommender_agent or RecommenderAgent(
            vector_store=vector_store
        )
        self.profile_agent = profile_agent or ProfileAgent()

        # Conversation context (Milestone 4)
        self.conversation_history: dict = {}  # user_id -> list of (query, response) tuples

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

        log_info(
            "orchestrator_initialized",
            with_profile_agent=True,
            with_recommender_agent=True,
            conversation_context=True,
        )

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
        log_info(
            "profile_loaded_for_query",
            user_id=user_id,
            has_preferences=len(profile.favorite_genres) > 0 or len(profile.favorite_artists) > 0,
        )

        # Decide routing
        use_rag = intent == "recommendation"

        log_agent_routing(
            agent_name="orchestrator",
            decision="recommender_agent" if use_rag else "fallback",
            user_query=query[:100],  # Log first 100 chars
        )

        if use_rag:
            response = self._handle_recommendation_query(query, profile, user_id)
        else:
            response = self._handle_fallback(query)

        # Store in conversation history
        self._add_to_history(user_id, query, response)

        return response

    def _add_to_history(self, user_id: str, query: str, response: str):
        """Add query and response to conversation history."""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        self.conversation_history[user_id].append({
            "query": query,
            "response": response[:200],  # Store truncated response
        })

        # Keep only last 10 interactions
        if len(self.conversation_history[user_id]) > 10:
            self.conversation_history[user_id] = self.conversation_history[user_id][-10:]

        log_info(
            "conversation_history_updated",
            user_id=user_id,
            history_length=len(self.conversation_history[user_id]),
        )

    def get_conversation_history(self, user_id: str) -> list:
        """Get conversation history for a user."""
        return self.conversation_history.get(user_id, [])

    def _handle_recommendation_query(
        self, query: str, profile: "UserProfile", user_id: str
    ) -> str:
        """
        Handle recommendation queries by delegating to RecommenderAgent.

        Args:
            query: User query
            profile: User profile with preferences
            user_id: User identifier for context

        Returns:
            Formatted response with event recommendations
        """
        log_info(
            "delegating_to_recommender_agent",
            query=query[:100],
            user_id=user_id,
        )

        # Delegate to RecommenderAgent
        results = self.recommender_agent.recommend(
            query=query,
            profile=profile,
            k=5,
        )

        # Format recommendations
        response = self.recommender_agent.format_recommendations(results)

        log_info("recommendation_response_generated", num_results=len(results))
        return response

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
