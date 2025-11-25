"""Recommendation tools for ADK agents.

These tools provide event recommendation operations that can be used by ADK agents:
- Searching for events via RAG vector store
- Ranking events based on user preferences
- Formatting recommendations for display

All tools are stateless and use dependency injection for vector store and ranker.
"""

from typing import Any, Optional

from google.adk import tool

from agents.event_ranker import EventRanker
from memory.models import UserProfile
from observability import log_error, log_info
from rag.vector_store import VectorStore


# Global instances (can be replaced with dependency injection)
_vector_store: Optional[VectorStore] = None
_event_ranker: Optional[EventRanker] = None


def initialize_recommendation_tools(
    vector_store: Optional[VectorStore] = None,
    event_ranker: Optional[EventRanker] = None,
) -> None:
    """Initialize the recommendation tools with vector store and ranker dependencies.

    This must be called before using the tools, typically during application startup.

    Args:
        vector_store: VectorStore instance for RAG queries
        event_ranker: EventRanker instance for LLM-based ranking
    """
    global _vector_store, _event_ranker
    _vector_store = vector_store
    _event_ranker = event_ranker
    log_info(
        "recommendation_tools_initialized",
        has_vector_store=vector_store is not None,
        has_ranker=event_ranker is not None,
    )


def _get_vector_store() -> Optional[VectorStore]:
    """Get the vector store instance."""
    return _vector_store


def _get_event_ranker() -> Optional[EventRanker]:
    """Get the event ranker instance."""
    return _event_ranker


@tool
def recommend_events_tool(
    query: str,
    user_id: str,
    user_profile: Optional[dict[str, Any]] = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Search and recommend cultural events based on user query and preferences.

    This tool performs semantic search over a database of cultural events (exhibitions,
    performances, galleries) and ranks them based on:
    - Semantic similarity to the user's query
    - User's stated preferences (favorite/disliked genres, artists)
    - Geographic proximity to the user's location
    - LLM-based contextual ranking

    The tool will return an empty list if the vector store is not available.

    Args:
        query: User's natural language search query (e.g., "contemporary art exhibitions")
        user_id: Unique identifier for the user
        user_profile: Optional dictionary containing user preferences with keys:
            - location: User's location (e.g., "Barcelona")
            - favorite_genres: List of genres the user likes
            - disliked_genres: List of genres the user dislikes
            - favorite_artists: List of favorite artists
        k: Number of recommendations to return (default: 5)

    Returns:
        List of dictionaries, each representing a recommended event with fields:
        - title: Event title
        - venue_name: Venue where the event takes place
        - description: Event description
        - start_date: Event start date
        - end_date: Event end date (optional)
        - genres: List of genres/tags
        - price: Price information
        - url: Link to event details
        - score: Relevance score (0.0-1.0)
        - reasoning: Why this event was recommended (if LLM ranking enabled)

    Example:
        >>> events = recommend_events_tool(
        ...     query="contemporary art",
        ...     user_id="user123",
        ...     user_profile={"favorite_genres": ["sculpture"], "location": "Barcelona"},
        ...     k=5
        ... )
        >>> print(events[0]["title"])
        "Contemporary Sculpture Exhibition"
    """
    log_info(
        "recommendation_tool_called",
        query=query[:100],
        user_id=user_id,
        has_profile=user_profile is not None,
        k=k,
    )

    vector_store = _get_vector_store()

    # Check if vector store is available
    if vector_store is None:
        log_error(
            "vector_store_not_available_in_tool",
            message="Cannot generate recommendations without vector store",
        )
        return []

    # Convert user_profile dict to UserProfile object if provided
    profile_obj = None
    if user_profile:
        try:
            profile_obj = UserProfile(**user_profile)
        except Exception as e:
            log_error(
                "failed_to_parse_user_profile",
                error=str(e),
                user_profile=user_profile,
            )

    # Query vector store with profile-aware scoring
    results = vector_store.query(
        query,
        k=k,
        profile=profile_obj,
        filters={},
    )

    # Apply LLM-based ranking if ranker is available and we have a profile
    event_ranker = _get_event_ranker()
    if profile_obj and event_ranker:
        log_info("applying_llm_ranking_in_tool", num_results=len(results))
        results = event_ranker.rank_events(results, profile_obj, user_query=query)
    else:
        # No profile or ranker, sort by RAG score
        results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)

    log_info(
        "recommendations_generated_by_tool",
        num_results=len(results),
        has_preferences=profile_obj is not None and len(profile_obj.favorite_genres) > 0,
    )

    # Convert results to dicts for ADK serialization
    result_dicts = []
    for result in results:
        if hasattr(result, "model_dump"):
            result_dicts.append(result.model_dump())
        elif hasattr(result, "dict"):
            result_dicts.append(result.dict())
        elif isinstance(result, dict):
            result_dicts.append(result)
        else:
            # Fallback: try to extract common attributes
            result_dict = {
                "title": getattr(result, "title", "Unknown"),
                "venue_name": getattr(result, "venue_name", "Unknown"),
                "description": getattr(result, "description", ""),
                "score": getattr(result, "score", 0.0),
            }
            result_dicts.append(result_dict)

    return result_dicts
