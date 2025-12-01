"""Recommendation tools for ADK agents.

These tools provide event recommendation operations that can be used by ADK agents:
- Searching for events via RAG vector store
- Ranking events based on user preferences
- Formatting recommendations for display

All tools use closure pattern for dependency injection (no global state).
"""

from typing import Any, Callable, Optional, TYPE_CHECKING
from datetime import date, datetime
import time

from agents.event_ranker import EventRanker
from memory.models import UserProfile
from observability import log_error, log_info

if TYPE_CHECKING:
    # Only imported for type checking to avoid heavy runtime dependencies
    from rag.vector_store import VectorStore


def create_recommendation_tools(
    vector_store: Optional["VectorStore"] = None,
    event_ranker: Optional[EventRanker] = None,
) -> Callable[..., dict[str, Any]]:
    """Factory function that creates recommendation tool with dependencies captured in closure.

    Args:
        vector_store: VectorStore instance for RAG queries (optional)
        event_ranker: EventRanker instance for LLM-based ranking (optional)

    Returns:
        recommend_events_tool function with dependencies captured

    Example:
        >>> vector_store = VectorStore()
        >>> event_ranker = create_event_ranker()
        >>> recommend_tool = create_recommendation_tools(vector_store, event_ranker)
        >>> agent = Agent(tools=[recommend_tool], ...)
    """
    log_info(
        "recommendation_tools_created",
        has_vector_store=vector_store is not None,
        has_ranker=event_ranker is not None,
    )

    def recommend_events_tool(
        query: str,
        user_id: str,
        user_profile: Optional[dict[str, Any]] = None,
        k: int = 5,
    ) -> dict[str, Any]:
        """Search and recommend cultural events returning structured envelope.

        Performs semantic search + optional LLM ranking and returns:
        {
          "query": <str>,
          "profile_used": <bool>,
          "ranking_strategy": "llm"|"rag",
          "ranking_fallback": <bool>,
          "events": [
             {
               "event_id": ..., "title": ..., "venue_name": ...,
               "description": ..., "genres": [...],
               "start_date": ..., "end_date": ..., "cost_range": ..., "url": ...,
               "score": <float>,
               "distance_km": <float|None>,
               "distance_category": <str|None>,
               "reasoning": <str>
             }, ...
          ]
        }

        Returns empty envelope with events=[] if vector store unavailable.

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
            Envelope dict as described above.

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

        # Check if vector store is available (captured from closure)
        if vector_store is None:
            log_error(
                "vector_store_not_available_in_tool",
                message="Cannot generate recommendations without vector store",
            )
            return {
                "query": query,
                "profile_used": user_profile is not None,
                "ranking_strategy": "none",
                "ranking_fallback": False,
                "events": [],
            }

        # Convert user_profile dict to UserProfile object if provided.
        # Tool callers often pass profile dicts without user_id; in that case
        # we default user_id from the tool's user_id argument to keep parsing
        # robust and avoid noisy validation errors.
        profile_obj = None
        if user_profile:
            try:
                profile_data = dict(user_profile)
                profile_data.setdefault("user_id", user_id)
                profile_obj = UserProfile(**profile_data)
            except Exception as e:
                log_error(
                    "failed_to_parse_user_profile",
                    error=str(e),
                    user_profile=user_profile,
                )

        # Query vector store with profile-aware scoring
        rag_ms: Optional[int] = None
        rank_ms: Optional[int] = None
        try:
            t_q = time.time()
            results = vector_store.query(
                query,
                k=k,
                profile=profile_obj,
                filters={},
            )
            rag_ms = int((time.time() - t_q) * 1000)
        except Exception as e:  # pragma: no cover - defensive, but we add tests
            log_error(
                "vector_store_query_failed_in_tool",
                error=str(e),
                error_type=type(e).__name__,
                user_id=user_id,
                query=query,
            )
            return {
                "query": query,
                "profile_used": profile_obj is not None,
                "ranking_strategy": "none",
                "ranking_fallback": True,
                "events": [],
            }

        # Filter out events that have already ended (end_date < today), but only
        # when we have end_date information. This applies consistently to both
        # local and Vertex-backed SearchResult objects.
        from datetime import date as _date_type  # avoid name clash with imported date

        today = _date_type.today()
        filtered_results: list[Any] = []
        expired_count = 0
        for r in results:
            end_val = getattr(r, "end_date", None)
            if end_val is None:
                filtered_results.append(r)
                continue
            try:
                if isinstance(end_val, str):
                    end_dt = _date_type.fromisoformat(end_val)
                else:
                    end_dt = end_val
            except Exception:
                # If we can't parse the date, keep the event rather than
                # accidentally dropping valid recommendations.
                filtered_results.append(r)
                continue
            if end_dt >= today:
                filtered_results.append(r)
            else:
                expired_count += 1

        if expired_count:
            log_info(
                "recommendation_filtered_past_events",
                user_id=user_id,
                query=query[:80],
                expired=expired_count,
                remaining=len(filtered_results),
                today=str(today),
            )

        results = filtered_results

        # Apply LLM-based ranking if ranker is available and we have a profile
        ranking_strategy = "rag"
        ranking_fallback = False
        if profile_obj and event_ranker:
            log_info("applying_llm_ranking_in_tool", num_results=len(results))
            before_titles = [r.title for r in results]
            try:
                t_rank = time.time()
                results = event_ranker.rank_events(results, profile_obj, user_query=query)
                rank_ms = int((time.time() - t_rank) * 1000)
                ranking_strategy = "llm"
                after_titles = [r.title for r in results]
                if before_titles == after_titles:
                    # If identical order, consider fallback (LLM may have failed silently)
                    ranking_fallback = True
            except Exception as e:
                log_error(
                    "llm_ranking_exception_in_tool",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
                ranking_strategy = "rag"
                ranking_fallback = True
        else:
            results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
            rank_ms = None

        log_info(
            "recommendations_generated_by_tool",
            num_results=len(results),
            has_preferences=profile_obj is not None and len(profile_obj.favorite_genres) > 0,
        )

        # Convert results to dicts for ADK serialization
        # Distance & reasoning builder
        def _distance_category(d: Optional[float]) -> Optional[str]:
            if d is None:
                return None
            if d < 1:
                return "nearby"
            if d < 3:
                return "walkable"
            if d < 10:
                return "transit"
            return "far"

        # Geocode user location if available for distance calculations
        user_coords = None
        if profile_obj and profile_obj.location:
            try:
                from tools.geocoder import geocoder_tool
                user_coords = geocoder_tool.geocode(profile_obj.location)
            except Exception as e:
                log_error(
                    "geocode_failed_in_recommend_tool",
                    error=str(e),
                    location=profile_obj.location,
                )
                user_coords = None

        favorite_genres_set = set(g.lower() for g in (profile_obj.favorite_genres if profile_obj else []))
        disliked_genres_set = set(g.lower() for g in (profile_obj.disliked_genres if profile_obj else []))
        favorite_artists_set = set(a.lower() for a in (profile_obj.favorite_artists if profile_obj else []))

        def _json_safe(value: Any) -> Any:
            """Recursively convert date/datetime objects to JSON-serializable strings."""
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, dict):
                return {k: _json_safe(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_json_safe(v) for v in value]
            return value

        result_dicts = []
        for result in results:
            # Raw base dict
            base = result.model_dump() if hasattr(result, "model_dump") else (
                result.dict() if hasattr(result, "dict") else {}
            )
            base = _json_safe(base)

            # Compute distance if coords available
            distance_km = None
            if user_coords and getattr(result, "venue_latitude", None) and getattr(result, "venue_longitude", None):
                try:
                    from tools.geocoder import geocoder_tool
                    distance_km = geocoder_tool.calculate_distance(
                        user_coords["lat"],
                        user_coords["lon"],
                        result.venue_latitude,
                        result.venue_longitude,
                    )
                except Exception as e:
                    log_error(
                        "distance_calc_failed",
                        error=str(e),
                        event_id=getattr(result, "event_id", "unknown"),
                    )
                    distance_km = None

            dist_cat = _distance_category(distance_km)

            # Reasoning builder
            reasoning_parts = []
            genres_lower = [g.lower() for g in getattr(result, "genres", [])]
            fav_matches = [g for g in genres_lower if g in favorite_genres_set]
            if fav_matches:
                reasoning_parts.append(f"matches favorite genre(s): {', '.join(fav_matches[:3])}")
            dis_matches = [g for g in genres_lower if g in disliked_genres_set]
            if dis_matches:
                reasoning_parts.append(f"avoids disliked genres except: {', '.join(dis_matches[:2])}")
            # Artists (if model has artists attr)
            artists = getattr(result, "artists", []) or []
            artist_matches = [a for a in artists if a.lower() in favorite_artists_set]
            if artist_matches:
                reasoning_parts.append(f"features favorite artist(s): {', '.join(artist_matches[:2])}")
            if dist_cat:
                if distance_km is not None:
                    reasoning_parts.append(f"{dist_cat} ({round(distance_km, 2)} km)")
                else:
                    reasoning_parts.append(dist_cat)
            reasoning_parts.append(f"semantic score {round(getattr(result,'score',0.0),3)}")
            reasoning = "; ".join(reasoning_parts)

            enriched = {
                **base,
                "distance_km": distance_km,
                "distance_category": dist_cat,
                "reasoning": reasoning,
            }
            result_dicts.append(enriched)

        log_info(
            "recommendation_timing",
            query=query[:80],
            user_id=user_id,
            rag_ms=rag_ms,
            rank_ms=rank_ms,
            num_results=len(results),
            profile_used=profile_obj is not None,
            ranking_strategy=ranking_strategy,
        )

        return {
            "query": query,
            "profile_used": profile_obj is not None,
            "ranking_strategy": ranking_strategy,
            "ranking_fallback": ranking_fallback,
            "events": result_dicts,
        }

    return recommend_events_tool
