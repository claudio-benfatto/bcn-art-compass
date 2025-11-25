"""Orchestrator Agent - Multi-agent workflow coordinator.

Routes user queries to appropriate agents:
- ProfileAgent: User preferences and memory
- RecommenderAgent: Event recommendations with RAG

A2A-compliant for future agent-to-agent communication.
"""

from typing import TYPE_CHECKING, Optional

from agents.a2a_protocol import A2AAgent, A2AMessage, AgentCapability, MessageType
from agents.intent_detector import IntentDetector, create_intent_detector
from agents.profile_agent import ProfileAgent
from agents.recommender_agent import RecommenderAgent
from observability import log_agent_routing, log_error, log_info

if TYPE_CHECKING:
    from memory.models import UserProfile


def _create_vector_store():
    """Create the appropriate vector store based on config.

    Returns:
        VectorStore instance or None if creation fails.
        Returns None in cloud environments without proper setup,
        allowing the app to start without RAG capabilities.
    """
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
        log_error(
            "vector_store_creation_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        # Return None instead of exiting - allows app to start without RAG
        log_info("continuing_without_vector_store", reason="initialization_failed")
        return None
class OrchestratorAgent(A2AAgent):
    """
    Orchestrator for multi-agent workflow coordination.

    Responsibilities:
    - Detect user intent (preference_update, recommendation, general)
    - Load and update user profiles via ProfileAgent
    - Delegate recommendations to RecommenderAgent
    - Track conversation context for multi-turn interactions
    - Route queries to appropriate agents

    A2A-compliant for future multi-agent coordination.
    """

    def __init__(
        self,
        recommender_agent: Optional[RecommenderAgent] = None,
        profile_agent: Optional[ProfileAgent] = None,
        intent_detector: Optional[IntentDetector] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            recommender_agent: RecommenderAgent instance. If None, creates a new one
            profile_agent: ProfileAgent instance. If None, creates a new one
            intent_detector: IntentDetector instance. If None, creates one based on environment
        """
        # Initialize A2A protocol base
        super().__init__(agent_id="orchestrator_agent", name="OrchestratorAgent")

        # Register capabilities
        self.register_capability(AgentCapability(
            name="process_query",
            description="Route user query to appropriate agents and return response",
            input_schema={"user_id": "string", "query": "string"},
            output_schema={"response": "string"},
        ))

        # Create vector store based on config
        vector_store = _create_vector_store()

        # Create event ranker for RecommenderAgent
        import os

        from agents.event_ranker import create_event_ranker

        api_key = os.getenv("GOOGLE_API_KEY")
        event_ranker = create_event_ranker(api_key=api_key)

        self.recommender_agent = recommender_agent or RecommenderAgent(
            event_ranker=event_ranker,
            vector_store=vector_store,
        )
        self.profile_agent = profile_agent or ProfileAgent()
        self.intent_detector = intent_detector or create_intent_detector()
        self.conversation_history: dict = {}  # user_id -> list of (query, response) tuples

        log_info(
            "orchestrator_initialized",
            with_profile_agent=True,
            with_recommender_agent=True,
            conversation_context=True,
        )



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
        intent = await self.intent_detector.detect_intent(query)
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

    def process(self, message: A2AMessage) -> A2AMessage:
        """
        Process A2A protocol message.

        Currently delegates to process_query for compatibility.
        Future: Full A2A routing between agents.

        Args:
            message: Input A2A message

        Returns:
            Response A2AMessage
        """
        if message.message_type != MessageType.REQUEST:
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content={"error": "Only REQUEST messages supported"},
                correlation_id=message.correlation_id,
            )

        action = message.content.get("action")

        if action == "process_query":
            user_id = message.content.get("user_id")
            query = message.content.get("query")
            response = self.process_query(user_id, query)

            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.RESPONSE,
                content={"response": response},
                correlation_id=message.correlation_id,
            )

        else:
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content={"error": f"Unknown action: {action}"},
                correlation_id=message.correlation_id,
            )
