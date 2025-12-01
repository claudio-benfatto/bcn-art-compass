import pytest

from datetime import date

from agents.event_ranker import EventRanker, GeminiEventRanker, Geocoder
from memory.models import UserProfile
from rag.models import SearchResult


class FakeLlmClientSuccess:
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[str] = []

    def generate_ranking(self, prompt: str) -> str:
        # Record the prompt for potential inspection
        self.calls.append(prompt)
        return self._response


class FakeLlmClientError:
    def generate_ranking(self, prompt: str) -> str:
        raise RuntimeError("boom")


class FakeGeocoder(Geocoder):
    def __init__(self, distance: float | None = None) -> None:
        self.distance = distance
        self.calls: list[tuple] = []

    def geocode(self, location: str) -> dict | None:
        self.calls.append(("geocode", location))
        # Simple deterministic coords; tests don't depend on exact values
        return {"lat": 41.0, "lon": 2.0}

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        self.calls.append(("distance", lat1, lon1, lat2, lon2))
        return self.distance if self.distance is not None else 0.0


class DummyRanker(EventRanker):
    """Concrete ranker for testing protected helpers like _extract_events_context."""

    def __init__(self, geocoder: Geocoder | None = None) -> None:
        super().__init__(geocoder=geocoder)

    def rank_events(self, results, profile, user_query: str = ""):
        return results


def _make_result(event_id: str, title: str, score: float) -> SearchResult:
    return SearchResult(
        event_id=event_id,
        title=title,
        description="desc",
        venue_name="venue",
        genres=["sculpture"],
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        cost_range="free",
        score=score,
        url="http://example.com",
        venue_latitude=None,
        venue_longitude=None,
    )


def _make_profile() -> UserProfile:
    return UserProfile(
        user_id="u1",
        location=None,
        favorite_genres=["sculpture"],
        disliked_genres=[],
        favorite_artists=[],
    )


def test_gemini_ranker_applies_valid_llm_ranking_order():
    """When LLM returns a valid permutation, results should be reordered accordingly."""
    # Two results with different scores
    r1 = _make_result("e1", "First", 0.2)
    r2 = _make_result("e2", "Second", 0.9)
    results = [r1, r2]
    profile = _make_profile()

    # LLM says: "2, 1"
    client = FakeLlmClientSuccess("2, 1")
    ranker = GeminiEventRanker(api_key="dummy", client=client)

    ranked = ranker.rank_events(results, profile, user_query="anything")

    assert [r.event_id for r in ranked] == ["e2", "e1"]
    # Ensure we actually called the fake client
    assert len(client.calls) == 1
    assert "Events to rank:" in client.calls[0]


def test_gemini_ranker_invalid_ranking_falls_back_to_score_sort():
    """If LLM returns invalid ranking indices, fall back to score-based order."""
    r1 = _make_result("e1", "LowScore", 0.1)
    r2 = _make_result("e2", "HighScore", 0.9)
    results = [r1, r2]
    profile = _make_profile()

    # Invalid: refers to 1 twice
    client = FakeLlmClientSuccess("1, 1")
    ranker = GeminiEventRanker(api_key="dummy", client=client)

    ranked = ranker.rank_events(results, profile)

    # Should be sorted by score descending, not by the invalid LLM order
    assert [r.event_id for r in ranked] == ["e2", "e1"]


def test_gemini_ranker_exception_from_client_falls_back_to_score_sort():
    """If LLM client raises, ranker should catch and fall back to score-based order."""
    r1 = _make_result("e1", "LowScore", 0.1)
    r2 = _make_result("e2", "HighScore", 0.9)
    results = [r1, r2]
    profile = _make_profile()

    ranker = GeminiEventRanker(api_key="dummy", client=FakeLlmClientError())

    ranked = ranker.rank_events(results, profile)

    # Again, expect pure score-based ordering
    assert [r.event_id for r in ranked] == ["e2", "e1"]


def test_gemini_ranker_does_not_call_client_when_no_results():
    """Guard: with empty results, client should not be invoked at all."""
    profile = _make_profile()
    client = FakeLlmClientSuccess("1")
    ranker = GeminiEventRanker(api_key="dummy", client=client)

    ranked = ranker.rank_events([], profile)

    assert ranked == []
    assert client.calls == []


def test_extract_events_context_truncates_description_and_formats_distance():
    """_extract_events_context should truncate description and round distance."""
    long_desc = "x" * 300
    # Provide venue coordinates so distance calculation is exercised
    base = _make_result("e1", "Title", 0.5)
    result = base.model_copy(
        update={
            "description": long_desc,
            "venue_latitude": 41.3851,
            "venue_longitude": 2.1734,
        }
    )
    user_coords = {"lat": 41.0, "lon": 2.0}

    geocoder = FakeGeocoder(distance=1.234)
    ranker = DummyRanker(geocoder=geocoder)

    ctx_list = ranker._extract_events_context([result], user_coords)
    assert len(ctx_list) == 1
    ctx = ctx_list[0]

    # Description truncated to 250 chars
    assert len(ctx["description"]) == 250
    assert ctx["description"] == long_desc[:250]

    # Distance rounded to 2 decimals
    assert ctx["distance_km"] == round(1.234, 2)


def test_extract_events_context_unknown_distance_without_coords():
    """If no user coords or venue coords, distance_km should be 'unknown'."""
    result = _make_result("e1", "Title", 0.5)
    user_coords = None

    geocoder = FakeGeocoder(distance=10.0)
    ranker = DummyRanker(geocoder=geocoder)

    ctx_list = ranker._extract_events_context([result], user_coords)
    ctx = ctx_list[0]
    assert ctx["distance_km"] == "unknown"


def test_extract_events_context_unknown_distance_without_venue_coords():
    """If venue coords are missing, distance_km should be 'unknown' and geocoder unused."""
    # Override venue_latitude / venue_longitude to None
    base = _make_result("e1", "Title", 0.5)
    result = base.model_copy(update={"venue_latitude": None, "venue_longitude": None})

    user_coords = {"lat": 41.0, "lon": 2.0}

    geocoder = FakeGeocoder(distance=10.0)
    ranker = DummyRanker(geocoder=geocoder)

    ctx_list = ranker._extract_events_context([result], user_coords)
    ctx = ctx_list[0]
    assert ctx["distance_km"] == "unknown"
    # No distance calls should have been made
    assert not any(call[0] == "distance" for call in geocoder.calls)



