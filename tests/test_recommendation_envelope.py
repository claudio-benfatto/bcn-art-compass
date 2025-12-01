import pytest
from datetime import date

from agents.tools.recommendation_tools import create_recommendation_tools
from rag.models import SearchResult


class DummyVectorStore:
    def query(self, query, k=5, profile=None, filters=None):
        # Return mock SearchResult-like objects
        class Result:
            def __init__(self, event_id, title, genres, score, venue_latitude=None, venue_longitude=None):
                self.event_id = event_id
                self.title = title
                self.genres = genres
                self.score = score
                self.venue_latitude = venue_latitude
                self.venue_longitude = venue_longitude
            def model_dump(self):
                return {
                    "event_id": self.event_id,
                    "title": self.title,
                    "genres": self.genres,
                    "score": self.score,
                    "venue_latitude": self.venue_latitude,
                    "venue_longitude": self.venue_longitude,
                }
        return [
            Result("e1", "Art Expo", ["contemporary", "sculpture"], 0.95, 41.3851, 2.1734),
            Result("e2", "Classic Show", ["classical", "painting"], 0.85, 41.3902, 2.1540),
        ]

class DummyEventRanker:
    def rank_events(self, results, profile, user_query=None):
        # Reverse order for test
        return list(reversed(results))


class FailingVectorStore:
    def query(self, query, k=5, profile=None, filters=None):
        raise RuntimeError("vector store boom")


class DateFilteringVectorStore:
    """Vector store that returns both past and future events for date filtering tests."""

    def query(self, query, k=5, profile=None, filters=None):
        today = date.today()
        past_end = today.replace(year=today.year - 1)
        future_end = today.replace(year=today.year + 1)

        past = SearchResult(
            event_id="past_event",
            title="Past Exhibition",
            description="An exhibition that already ended.",
            venue_name="Old Museum",
            genres=["painting"],
            start_date=past_end.replace(month=1, day=1),
            end_date=past_end,
            cost_range="€10",
            score=0.9,
            url="https://example.com/past",
            venue_latitude=None,
            venue_longitude=None,
        )
        future = SearchResult(
            event_id="future_event",
            title="Future Exhibition",
            description="An upcoming exhibition.",
            venue_name="New Museum",
            genres=["painting"],
            start_date=future_end.replace(month=1, day=1),
            end_date=future_end,
            cost_range="€12",
            score=0.8,
            url="https://example.com/future",
            venue_latitude=None,
            venue_longitude=None,
        )

        return [past, future][:k]

@pytest.fixture
def dummy_tools():
    vector_store = DummyVectorStore()
    event_ranker = DummyEventRanker()
    return create_recommendation_tools(vector_store, event_ranker)

def test_envelope_structure(dummy_tools):
    user_profile = {
        "user_id": "u1",
        "location": "Barcelona",
        "favorite_genres": ["sculpture"],
        "disliked_genres": ["video art"],
        "favorite_artists": ["Picasso"],
    }
    tool = dummy_tools
    result = tool(
        query="sculpture events",
        user_id="u1",
        user_profile=user_profile,
        k=2,
    )
    assert isinstance(result, dict)
    assert set(result.keys()) >= {"query", "profile_used", "ranking_strategy", "ranking_fallback", "events"}
    assert result["profile_used"] is True
    assert result["ranking_strategy"] in ("llm", "rag")
    assert isinstance(result["events"], list)
    assert len(result["events"]) == 2
    for event in result["events"]:
        assert set(event.keys()) >= {
            "event_id", "title", "genres", "score",
            "distance_km", "distance_category", "reasoning"
        }
        assert isinstance(event["reasoning"], str)
        # Reasoning should mention favorite genre if present
        if "sculpture" in [g.lower() for g in event["genres"]]:
            assert "sculpture" in event["reasoning"].lower()

def test_empty_vector_store():
    tool = create_recommendation_tools(None, None)
    result = tool(
        query="anything",
        user_id="u2",
        user_profile=None,
        k=2,
    )
    assert isinstance(result, dict)
    assert result["events"] == []
    assert result["ranking_strategy"] == "none"
    assert result["ranking_fallback"] is False
    assert result["profile_used"] is False
    assert result["query"] == "anything"


def test_vector_store_exception_falls_back_cleanly():
    """If the vector store raises, tool should return an empty but well-formed envelope."""
    tool = create_recommendation_tools(FailingVectorStore(), None)
    result = tool(
        query="boom",
        user_id="u3",
        user_profile={"user_id": "u3"},
        k=3,
    )

    assert isinstance(result, dict)
    assert result["events"] == []
    assert result["ranking_strategy"] == "none"
    # We had a usable profile but fell back due to an internal error
    assert result["ranking_fallback"] is True
    assert result["profile_used"] is True


def test_recommendation_filters_past_events_by_end_date():
    """recommend_events_tool should not return events that have already ended."""
    tool = create_recommendation_tools(DateFilteringVectorStore(), None)

    result = tool(
        query="any art exhibitions",
        user_id="u4",
        user_profile=None,
        k=5,
    )

    events = result["events"]
    # Only the future event should remain after filtering
    ids = [e["event_id"] for e in events]
    assert "past_event" not in ids
    assert "future_event" in ids


def test_recommend_tool_accepts_profile_without_user_id():
    """User profile dicts coming from tools may lack user_id; tool should still parse them."""
    tool = create_recommendation_tools(DummyVectorStore(), DummyEventRanker())

    # Profile missing user_id (common from profile_tools/orchestrator payloads)
    profile_without_id = {
        "location": "Barcelona",
        "favorite_genres": ["impressionism", "classical"],
        "disliked_genres": ["modern", "abstract"],
        "favorite_artists": [],
    }

    result = tool(
        query="museum of art in the morning",
        user_id="cli_user_123",
        user_profile=profile_without_id,
        k=2,
    )

    assert isinstance(result, dict)
    assert result["profile_used"] is True
    # Should still return events and not raise/return empty due to profile parsing
    assert isinstance(result["events"], list)
    assert len(result["events"]) == 2
