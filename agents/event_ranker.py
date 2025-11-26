"""Event ranking interface and implementations.

Provides a standard interface for ranking events and concrete implementations
for different LLM backends (Gemini, Ollama).
"""

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Union

from observability import log_error, log_info
from rag.models import EventWithVenue, SearchResult
from tools.geocoder import geocoder_tool

if TYPE_CHECKING:
    from memory.models import UserProfile


class EventRanker(ABC):
    """Abstract base class for event ranking."""

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

    def _build_ranking_prompt(
        self,
        events_context: List[dict],
        profile: "UserProfile",
        user_query: str = "",
    ) -> str:
        """
        Build comprehensive prompt with all ranking context.

        Args:
            events_context: List of event dictionaries with all details
            profile: User profile
            user_query: Original user search query

        Returns:
            Formatted prompt string
        """
        # Format user profile
        profile_text = f"""User Profile:
- Location: {profile.location or 'Not specified'}
- Favorite genres: {', '.join(profile.favorite_genres) if profile.favorite_genres else 'None'}
- Favorite artists: {', '.join(profile.favorite_artists) if profile.favorite_artists else 'None'}
- Disliked genres: {', '.join(profile.disliked_genres) if profile.disliked_genres else 'None'}
"""

        # Format events
        events_text = "\n\n".join([
            f"""{e['index']}. {e['title']}
   Venue: {e['venue']}
   Genres: {', '.join(e['genres'][:3])}
   Artists: {', '.join(e['artists'][:2]) if e['artists'] else 'N/A'}
   RAG Score: {e['rag_score']} (semantic similarity to query)
   Distance: {e['distance_km']} km from user
   Description: {e['description']}"""
            for e in events_context
        ])

        query_text = f"User Query: \"{user_query}\"\n" if user_query else ""

        prompt = f"""You are an expert art curator helping rank cultural events for a user.

{query_text}{profile_text}

Events to rank:
{events_text}

Task: Rank these events from most to least relevant for this user.

Consider ALL THREE factors:
1. **User query**: What is the user specifically looking for? This is their immediate intent.
2. **User preferences**: Favor favorite genres/artists, avoid disliked genres (long-term profile)
3. **Location**: Closer events are more convenient, but amazing matches may be worth traveling for
4. **RAG score**: Shows semantic similarity between the event and the user's query

Apply nuanced reasoning. For example:
- If user asks "sculpture exhibitions", prioritize sculpture events even if farther away
- An event matching the query + favorite genre beats one that only matches profile
- Avoid disliked genres even if they match the query
- Balance query intent with profile preferences and location
- Very high RAG scores indicate strong query-event match - weight them heavily

Respond with ONLY a comma-separated list of event numbers in your preferred ranking order.
Example: 3, 1, 5, 2, 4

Your ranking:"""

        return prompt

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
                distance_km = geocoder_tool.calculate_distance(
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


class GeminiEventRanker(EventRanker):
    """Event ranker using Google Gemini."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini event ranker.

        Args:
            api_key: Google API key
            model: Gemini model to use
        """
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        self.model = model
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
            user_coords = geocoder_tool.geocode(profile.location)
            if user_coords:
                log_info(
                    "user_location_resolved",
                    location=profile.location,
                    coords=f"{user_coords['lat']},{user_coords['lon']}",
                )

        # Extract event context
        events_context = self._extract_events_context(results, user_coords)

        # Build prompt
        prompt = self._build_ranking_prompt(events_context, profile, user_query)

        try:
            log_info("calling_llm_for_ranking", num_events=len(results), backend="gemini")

            response = self.client.generate_content(prompt)
            ranking_text = response.text.strip()

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


class OllamaEventRanker(EventRanker):
    """Event ranker using Ollama (local LLM)."""

    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama event ranker.

        Args:
            model: Ollama model to use
            base_url: Ollama server URL
        """
        self.model = model
        self.base_url = base_url
        log_info("event_ranker_initialized", backend="ollama", model=model)

    def rank_events(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        profile: "UserProfile",
        user_query: str = "",
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """Rank events using Ollama."""
        if not results:
            return results

        log_info(
            "applying_llm_ranking",
            num_events=len(results),
            backend="ollama",
            has_user_location=bool(profile.location),
        )

        # Get user coordinates
        user_coords = None
        if profile.location:
            user_coords = geocoder_tool.geocode(profile.location)
            if user_coords:
                log_info(
                    "user_location_resolved",
                    location=profile.location,
                    coords=f"{user_coords['lat']},{user_coords['lon']}",
                )

        # Extract event context
        events_context = self._extract_events_context(results, user_coords)

        # Build ranking prompt with query, profile, and location
        prompt = self._build_ranking_prompt(events_context, profile, user_query)

        try:
            import requests

            log_info("calling_llm_for_ranking", num_events=len(results), backend="ollama")

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=30
            )
            response.raise_for_status()
            ranking_text = response.json()["response"].strip()

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


def create_event_ranker(api_key: str = None) -> EventRanker:
    """
    Factory function to create event ranker based on environment.

    Prefers Gemini if api_key provided, otherwise uses Ollama.

    Args:
        api_key: Optional Google API key for Gemini

    Returns:
        EventRanker instance
    """
    if api_key:
        return GeminiEventRanker(api_key=api_key)

    # Use Ollama for local development
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaEventRanker(model=model, base_url=base_url)
