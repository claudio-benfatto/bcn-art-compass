"""
Recommender Agent - handles event recommendations with profile-based ranking.

This agent is responsible for:
- Querying the RAG vector store
- Applying profile-based scoring adjustments
- Ranking and filtering results
- Formatting recommendations for users

Part of Milestone 4: Clean Multi-Agent Workflow
"""

from typing import TYPE_CHECKING, List, Optional

from observability import log_info
from rag.models import EventWithVenue
from rag.vector_store import VectorStore

if TYPE_CHECKING:
    from memory.models import UserProfile


class RecommenderAgent:
    """
    Agent specialized in generating personalized event recommendations.

    Uses RAG for semantic search and applies user profile preferences
    to refine and rank results.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Initialize the recommender agent.

        Args:
            vector_store: VectorStore instance for RAG queries. If None, creates a new one
        """
        self.vector_store = vector_store or VectorStore()
        log_info("recommender_agent_initialized")

    def recommend(
        self,
        query: str,
        profile: Optional["UserProfile"] = None,
        k: int = 5,
        filters: Optional[dict] = None,
    ) -> List[EventWithVenue]:
        """
        Generate personalized event recommendations.

        Args:
            query: User's search query
            profile: User profile with preferences (optional)
            k: Number of results to return
            filters: Additional filters (e.g., date range, location)

        Returns:
            List of EventWithVenue objects, ranked by relevance and preferences

        Example:
            >>> agent = RecommenderAgent()
            >>> results = agent.recommend("contemporary art", profile=user_profile, k=5)
        """
        log_info(
            "generating_recommendations",
            query=query[:100],
            has_profile=profile is not None,
            k=k,
        )

        # Query vector store with profile-aware scoring
        results = self.vector_store.query(
            query,  # Positional argument
            k=k,
            profile=profile,
            filters=filters or {},
        )

        if profile:
            # Apply additional ranking logic based on profile
            results = self._apply_advanced_ranking(results, profile)

        log_info(
            "recommendations_generated",
            num_results=len(results),
            has_preferences=profile is not None and len(profile.favorite_genres) > 0,
        )

        return results

    def _apply_advanced_ranking(
        self,
        results: List[EventWithVenue],
        profile: "UserProfile",
    ) -> List[EventWithVenue]:
        """
        Apply advanced ranking logic beyond basic scoring.

        This method can be extended with more sophisticated ranking:
        - Multi-criteria scoring
        - Diversity adjustments
        - Temporal relevance
        - Location proximity (when available)

        Args:
            results: List of results from vector store
            profile: User profile with preferences

        Returns:
            Re-ranked results
        """
        # Note: Basic scoring is already done in vector_store.query()
        # This method is a placeholder for future enhancements like:
        # - Diversity: avoid too many similar events
        # - Recency: prefer newer events
        # - Popularity: consider user engagement metrics
        # - Location: prefer closer venues (requires geocoder)

        # For now, trust the vector store's profile-aware scoring
        return results

    def format_recommendations(
        self,
        results: List[EventWithVenue],
        include_reasoning: bool = False,
    ) -> str:
        """
        Format recommendations into user-friendly text.

        Args:
            results: List of EventWithVenue objects
            include_reasoning: Whether to include why each event was recommended

        Returns:
            Formatted string with recommendations
        """
        if not results:
            return "I couldn't find any events matching your query. Could you try rephrasing?"

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
