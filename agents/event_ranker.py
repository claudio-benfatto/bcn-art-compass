"""Event ranking interface and implementations.

Provides a standard interface for ranking events and a concrete implementation
for a Gemini-based LLM ranker.
"""

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Protocol, Union

from observability import log_error, log_info
from agents.prompts import get_event_ranking_prompt
from rag.models import EventWithVenue, SearchResult
from tools.geocoder import geocoder_tool

if TYPE_CHECKING:
    from memory.models import UserProfile


class Geocoder(Protocol):
    """Protocol for geocoding and distance calculations used by rankers."""

    def geocode(self, location: str) -> dict | None:  # pragma: no cover - interface only
        ...

    def calculate_distance(  # pragma: no cover - interface only
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        ...


class EventRanker(ABC):
    """Abstract base class for event ranking."""

    def __init__(self, geocoder: Geocoder | None = None) -> None:
        # Allow injecting a fake geocoder for tests; default to shared singleton.
        self._geocoder: Geocoder = geocoder or geocoder_tool

    @abstractmethod
    def rank_events(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        profile: "UserProfile",
        user_query: str = "",
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """
        Rank events based on user query, profile, and location.

        Args:
            results: List of events from RAG search with scores
            profile: User profile with preferences and location
            user_query: Original user search query

        Returns:
            Re-ranked list of results
        """
        pass

    def _extract_events_context(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        user_coords: dict = None,
    ) -> List[dict]:
        """
        Extract event details and calculate distances.

        Args:
            results: List of events
            user_coords: User coordinates dict with 'lat' and 'lon' keys

        Returns:
            List of event context dictionaries
        """
        events_context = []
        for idx, result in enumerate(results):
            # Extract event details
            if isinstance(result, EventWithVenue):
                title = result.title
                description = result.description
                genres = result.genres
                artists = result.artists if hasattr(result, "artists") else []
                venue_name = result.venue.name
                venue_lat = result.venue.latitude
                venue_lon = result.venue.longitude
            else:  # SearchResult
                title = result.title
                description = result.description
                genres = result.genres
                artists = getattr(result, "artists", [])
                venue_name = result.venue_name
                venue_lat = result.venue_latitude
                venue_lon = result.venue_longitude

            rag_score = result.score if hasattr(result, "score") else 0.0

            # Calculate distance if possible
            distance_km = None
            if user_coords and venue_lat and venue_lon:
                distance_km = self._geocoder.calculate_distance(
                    user_coords["lat"], user_coords["lon"], venue_lat, venue_lon
                )

            events_context.append({
                "index": idx + 1,
                "title": title,
                "description": description[:250],
                "genres": genres,
                "artists": artists if artists else [],
                "venue": venue_name,
                "rag_score": round(rag_score, 3),
                "distance_km": round(distance_km, 2) if distance_km else "unknown",
            })

        return events_context

    def _parse_ranking_response(self, ranking_text: str) -> List[int]:
        """
        Parse LLM response to extract ranking indices.

        Args:
            ranking_text: Raw LLM response

        Returns:
            List of zero-based indices
        """
        import re
        ranking_indices = []
        for x in ranking_text.split(","):
            x = x.strip()
            # Extract first number found
            match = re.search(r"\d+", x)
            if match:
                ranking_indices.append(int(match.group()) - 1)
        return ranking_indices


class RankingLlmClient(Protocol):
    """Minimal protocol for an LLM client that can rank events given a prompt.

    This indirection allows us to inject fakes/doubles in tests and keep the
    EventRanker logic independent from a specific SDK or transport.
    """

    def generate_ranking(self, prompt: str) -> str:  # pragma: no cover - interface only
        ...


class GeminiLlmClient:
    """Concrete RankingLlmClient backed by google.generativeai."""

    def __init__(self, api_key: str, model: str) -> None:
        # Import inside constructor so tests can inject a fake client without
        # importing the heavy google.generativeai dependency.
        import google.generativeai as genai  # type: ignore[import-not-found]

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    def generate_ranking(self, prompt: str) -> str:
        response = self._model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        return text.strip()


class GeminiEventRanker(EventRanker):
    """Event ranker using Google Gemini."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        client: RankingLlmClient | None = None,
        geocoder: Geocoder | None = None,
    ) -> None:
        """
        Initialize Gemini event ranker.

        Args:
            api_key: Google API key
            model: Gemini model to use
            client: Optional pre-configured RankingLlmClient (for testing or custom wiring)
            geocoder: Optional Geocoder implementation (for testing or custom wiring)
        """
        super().__init__(geocoder=geocoder)
        self.model = model
        self._client: RankingLlmClient = client or GeminiLlmClient(api_key=api_key, model=model)
        log_info("event_ranker_initialized", backend="gemini", model=model)

    def rank_events(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        profile: "UserProfile",
        user_query: str = "",
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """Rank events using Gemini."""
        if not results:
            return results

        log_info(
            "applying_llm_ranking",
            num_events=len(results),
            backend="gemini",
            has_user_location=bool(profile.location),
        )

        # Get user coordinates
        user_coords = None
        if profile.location:
            user_coords = self._geocoder.geocode(profile.location)
            if user_coords:
                log_info(
                    "user_location_resolved",
                    location=profile.location,
                    coords=f"{user_coords['lat']},{user_coords['lon']}",
                )

        # Extract event context
        events_context = self._extract_events_context(results, user_coords)

        # Build prompt (centralized in agents.prompts)
        prompt = get_event_ranking_prompt(events_context, profile, user_query)

        try:
            log_info("calling_llm_for_ranking", num_events=len(results), backend="gemini")

            ranking_text = self._client.generate_ranking(prompt)

            log_info("llm_ranking_response", response=ranking_text[:200])

            # Parse ranking
            ranking_indices = self._parse_ranking_response(ranking_text)

            # Validate and apply ranking
            if len(ranking_indices) == len(results) and set(ranking_indices) == set(range(len(results))):
                reranked = [results[i] for i in ranking_indices]

                def get_title(r):
                    return r.title[:50] if hasattr(r, "title") else "unknown"

                log_info(
                    "llm_ranking_applied",
                    original_top=get_title(results[0]),
                    reranked_top=get_title(reranked[0]),
                )
                return reranked
            else:
                log_error(
                    "llm_ranking_invalid",
                    expected=len(results),
                    got=len(ranking_indices),
                    indices=ranking_indices,
                    reason="Invalid ranking from LLM, using RAG score order",
                )
                results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
                return results

        except Exception as e:
            log_error("llm_ranking_failed", error=str(e), error_type=type(e).__name__)
            results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
            return results



def create_event_ranker(api_key: str | None = None) -> EventRanker:
    """
    Factory function to create event ranker based on environment.

    Creates a Gemini-based event ranker.

    Args:
        api_key: Optional Google API key for Gemini

    Returns:
        EventRanker instance
    """
    if api_key is None:
        # Fallback to environment for convenience in CLI/API wiring
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No API key provided for event ranker. "
            "Set GOOGLE_API_KEY or pass api_key to create_event_ranker()."
        )

    return GeminiEventRanker(api_key=api_key)
