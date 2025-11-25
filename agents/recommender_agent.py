"""
Recommender Agent - handles event recommendations with profile-based ranking.

This agent is responsible for:
- Querying the RAG vector store
- Applying profile-based scoring adjustments
- Ranking and filtering results
- Formatting recommendations for users

A2A-compliant for future agent-to-agent communication.
"""

from typing import TYPE_CHECKING, List, Optional, Union

from agents.a2a_protocol import A2AAgent, A2AMessage, AgentCapability, MessageType
from agents.event_ranker import EventRanker, create_event_ranker
from observability import log_error, log_info
from rag.models import EventWithVenue, SearchResult
from rag.vector_store import VectorStore

if TYPE_CHECKING:
    from memory.models import UserProfile


class RecommenderAgent(A2AAgent):
    """
    Agent specialized in generating personalized event recommendations.

    Uses RAG for semantic search and applies user profile preferences
    to refine and rank results. Includes distance-based scoring when user
    location is available.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        event_ranker: Optional[EventRanker] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the recommender agent.

        Args:
            vector_store: VectorStore instance for RAG queries
            event_ranker: EventRanker instance for ranking results. If None, creates one
            api_key: Google API key for Gemini (used if event_ranker not provided)
        """
        # Initialize A2A protocol base
        super().__init__(agent_id="recommender_agent", name="RecommenderAgent")

        # Register capabilities
        self.register_capability(AgentCapability(
            name="recommend",
            description="Generate personalized event recommendations",
            input_schema={
                "query": "string",
                "profile": "UserProfile (optional)",
                "k": "integer (optional)",
            },
            output_schema={"recommendations": "list[EventWithVenue]"},
        ))

        # Store vector_store (may be None in cloud without proper setup)
        self.vector_store = vector_store

        # Initialize or use provided event ranker
        self.event_ranker = event_ranker or create_event_ranker(api_key=api_key)

        log_info(
            "recommender_agent_initialized",
            has_vector_store=vector_store is not None,
            has_ranker=self.event_ranker is not None,
        )

    def recommend(
        self,
        query: str,
        profile: Optional["UserProfile"] = None,
        k: int = 5,
        filters: Optional[dict] = None,
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """
        Generate personalized event recommendations.

        Args:
            query: User's search query
            profile: User profile with preferences (optional)
            k: Number of results to return
            filters: Additional filters (e.g., date range, location)

        Returns:
            List of EventWithVenue or SearchResult objects, ranked by relevance and preferences

        Example:
            >>> agent = RecommenderAgent()
            >>> results = agent.recommend("contemporary art", profile=user_profile, k=5)
        """
        log_info(
            "generating_recommendations",
            query=query[:100],
            has_profile=profile is not None,
            has_vector_store=self.vector_store is not None,
            k=k,
        )

        # Check if vector store is available
        if self.vector_store is None:
            log_error(
                "vector_store_not_available",
                message="Cannot generate recommendations without vector store",
            )
            return []

        # Query vector store with profile-aware scoring
        results = self.vector_store.query(
            query,
            k=k,
            profile=profile,
            filters=filters or {},
        )

        if profile and self.event_ranker:
            # Apply LLM-based ranking with query, profile, and location
            results = self.event_ranker.rank_events(results, profile, user_query=query)
        else:
            # No profile or ranker, sort by RAG score
            results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)

        log_info(
            "recommendations_generated",
            num_results=len(results),
            has_preferences=profile is not None and len(profile.favorite_genres) > 0,
        )

        return results

    def format_recommendations(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        include_reasoning: bool = False,
    ) -> str:
        """
        Format recommendations into user-friendly text.

        Args:
            results: List of EventWithVenue or SearchResult objects
            include_reasoning: Whether to include why each event was recommended

        Returns:
            Formatted string with recommendations
        """
        if not results:
            return self._format_no_results_message()

        response_lines = [f"I found {len(results)} events that might interest you:\n"]

        for i, result in enumerate(results, 1):
            response_lines.append(f"{i}. **{result.title}** at {result.venue_name}")
            response_lines.append(f"   {result.description[:150]}...")
            response_lines.append(f"   📅 {result.start_date} to {result.end_date}")
            response_lines.append(f"   🎨 {', '.join(result.genres[:3])}")
            response_lines.append(f"   💰 {result.cost_range}")
            response_lines.append(f"   🔗 {result.url}\n")

            if include_reasoning and hasattr(result, "score"):
                response_lines.append(f"   (Match score: {result.score:.3f})\n")

        return "\n".join(response_lines)

    def _format_no_results_message(self) -> str:
        """
        Generate a helpful message when no results are found.

        Returns:
            User-friendly message with suggestions
        """
        return """I couldn't find any events matching your query. Here are some suggestions:

🎨 **Try broader terms**: Instead of "cubist sculpture", try "sculpture" or "modern art"
📍 **Expand your area**: Consider nearby neighborhoods
📅 **Check different dates**: Some events might be seasonal
❤️ **Tell me your preferences**: Say "I like contemporary art" to help me learn

Would you like me to search for something else?"""

    def process(self, message: A2AMessage) -> A2AMessage:
        """
        Process A2A protocol message.

        Args:
            message: Input A2A message

        Returns:
            Response A2A message
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

        if action == "recommend":
            query = message.content.get("query")
            profile = message.content.get("profile")  # Could be dict or UserProfile
            k = message.content.get("k", 5)

            # Convert profile dict to UserProfile if needed
            if profile and isinstance(profile, dict):
                from memory.models import UserProfile
                profile = UserProfile(**profile)

            results = self.recommend(query=query, profile=profile, k=k)

            # Serialize results (works for both EventWithVenue and SearchResult)
            serialized_results = [
                {
                    "title": r.title,
                    "description": r.description,
                    "venue_name": r.venue_name if hasattr(r, "venue_name") else r.venue.name,
                }
                for r in results
            ]

            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.RESPONSE,
                content={"recommendations": serialized_results},
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
