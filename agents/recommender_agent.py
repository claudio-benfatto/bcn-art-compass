"""
Recommender Agent - handles event recommendations with profile-based ranking.

This agent is responsible for:
- Querying the RAG vector store
- Applying profile-based scoring adjustments
- Ranking and filtering results
- Formatting recommendations for users

Part of Milestone 4: Clean Multi-Agent Workflow
"""

from typing import TYPE_CHECKING, List, Optional, Union

from observability import log_info
from rag.models import EventWithVenue, SearchResult
from rag.vector_store import VectorStore
from tools.geocoder import geocoder_tool

if TYPE_CHECKING:
    from memory.models import UserProfile


class RecommenderAgent:
    """
    Agent specialized in generating personalized event recommendations.

    Uses RAG for semantic search and applies user profile preferences
    to refine and rank results. Includes distance-based scoring when user
    location is available.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Initialize the recommender agent.

        Args:
            vector_store: VectorStore instance for RAG queries. If None, creates a new one
        """
        self.vector_store = vector_store or VectorStore()
        self.geocoder = geocoder_tool
        log_info("recommender_agent_initialized")

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
        results: List[Union[EventWithVenue, SearchResult]],
        profile: "UserProfile",
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """
        Apply advanced ranking logic beyond basic scoring.

        Enhances results with:
        - Location proximity scoring (when user location is available)
        - Diversity adjustments (future)
        - Temporal relevance (future)

        Args:
            results: List of results from vector store
            profile: User profile with preferences

        Returns:
            Re-ranked results
        """
        # Apply location-based scoring if user has a location
        if profile.location:
            results = self._apply_location_scoring(results, profile.location)

        # Sort by score if available
        if results and hasattr(results[0], "score"):
            results.sort(key=lambda x: x.score, reverse=True)

        return results

    def _apply_location_scoring(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        user_location: str,
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """
        Apply distance-based scoring to prioritize nearby events.

        Args:
            results: List of events to score
            user_location: User's location (e.g., "Gràcia", "Barcelona")

        Returns:
            Results with adjusted scores based on proximity
        """
        # Get user coordinates
        user_coords = self.geocoder.geocode(user_location)
        if not user_coords:
            log_info("location_scoring_skipped", reason="user_location_not_found")
            return results

        user_lat, user_lon = user_coords["lat"], user_coords["lon"]
        log_info(
            "applying_location_scoring",
            user_location=user_location,
            user_coords=f"{user_lat},{user_lon}",
        )

        for event in results:
            # Get event coordinates - handle both EventWithVenue and SearchResult
            if isinstance(event, EventWithVenue):
                event_lat, event_lon = event.venue.latitude, event.venue.longitude
            else:  # SearchResult
                event_lat = event.venue_latitude
                event_lon = event.venue_longitude

            # Skip if coordinates missing
            if event_lat is None or event_lon is None:
                # Get event title for logging
                if hasattr(event, "title"):
                    event_title = event.title[:50]
                elif hasattr(event, "event"):
                    event_title = event.event.title[:50]
                else:
                    event_title = "unknown"

                log_info(
                    "location_scoring_skipped_for_event",
                    event_title=event_title,
                    reason="missing_coordinates"
                )
                continue

            # Calculate distance
            distance_km = self.geocoder.calculate_distance(
                user_lat, user_lon, event_lat, event_lon
            )

            # Apply proximity boost
            # Events within 2km: +0.15 boost
            # Events 2-5km: +0.10 boost
            # Events 5-10km: +0.05 boost
            # Events >10km: no boost
            if distance_km <= 2:
                proximity_boost = 0.15
            elif distance_km <= 5:
                proximity_boost = 0.10
            elif distance_km <= 10:
                proximity_boost = 0.05
            else:
                proximity_boost = 0.0

            # Add to score if available
            if hasattr(event, "score"):
                old_score = event.score
                event.score += proximity_boost

                # Get event title for logging
                if hasattr(event, "title"):
                    event_title = event.title[:50]
                elif hasattr(event, "event"):
                    event_title = event.event.title[:50]
                else:
                    event_title = "unknown"

                log_info(
                    "proximity_boost_applied",
                    event_title=event_title,
                    distance_km=round(distance_km, 2),
                    boost=proximity_boost,
                    old_score=round(old_score, 3),
                    new_score=round(event.score, 3),
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
