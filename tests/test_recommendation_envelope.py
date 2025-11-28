import pytest
from agents.tools.recommendation_tools import create_recommendation_tools

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
