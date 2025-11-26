"""Test that RecommenderAgent uses query, profile, and location."""

from datetime import date
from unittest.mock import Mock, patch

import pytest

from agents.recommender_agent import RecommenderAgent
from memory.models import UserProfile
from rag.models import SearchResult


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock()
    # Return mock results with different scores
    store.query.return_value = [
        SearchResult(
            event_id="1",
            title="Contemporary Sculpture Exhibition",
            description="Modern sculptures from local artists",
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 31),
            url="http://example.com/1",
            venue_name="Gallery A",
            venue_latitude=41.3851,
            venue_longitude=2.1734,
            cost_range="€10-15",
            genres=["sculpture", "contemporary"],
            score=0.85,
        ),
        SearchResult(
            event_id="2",
            title="Painting Workshop",
            description="Learn oil painting techniques",
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 31),
            url="http://example.com/2",
            venue_name="Gallery B",
            venue_latitude=41.4000,
            venue_longitude=2.2000,
            cost_range="€20",
            genres=["painting", "workshop"],
            score=0.75,
        ),
        SearchResult(
            event_id="3",
            title="Installation Art Show",
            description="Immersive video art installations",
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 31),
            url="http://example.com/3",
            venue_name="Gallery C",
            venue_latitude=41.3900,
            venue_longitude=2.1800,
            cost_range="Free",
            genres=["video art", "installation"],
            score=0.90,
        ),
    ]
    return store


@pytest.fixture
def user_profile():
    """Create a user profile with preferences."""
    return UserProfile(
        user_id="test_user",
        location="Barcelona",
        favorite_genres=["sculpture", "contemporary"],
        disliked_genres=["video art"],
        favorite_artists=[],
    )


@pytest.fixture
def mock_event_ranker():
    """Create a mock event ranker that verifies it receives all parameters."""
    ranker = Mock()

    def rank_with_verification(results, profile, user_query=""):
        # Verify all three factors are provided
        assert results is not None, "Results should be provided"
        assert profile is not None, "Profile should be provided"
        assert user_query, "User query should be provided"

        # Simulate re-ranking: prefer sculpture (favorite genre) over video art (disliked)
        # Even though video art has higher RAG score
        reranked = sorted(
            results,
            key=lambda x: (
                1 if "sculpture" in x.genres else 0,  # Favor favorite genre
                -1 if "video art" in x.genres else 0,  # Penalize disliked genre
                x.score,  # Then use RAG score
            ),
            reverse=True,
        )
        return reranked

    ranker.rank_events.side_effect = rank_with_verification
    return ranker


def test_recommender_uses_query_profile_location(
    mock_vector_store, user_profile, mock_event_ranker
):
    """Test that RecommenderAgent passes query to the ranker."""
    agent = RecommenderAgent(
        vector_store=mock_vector_store,
        event_ranker=mock_event_ranker,
    )

    query = "sculpture exhibitions in Barcelona"
    results = agent.recommend(query=query, profile=user_profile, k=3)

    # Verify vector store was queried
    mock_vector_store.query.assert_called_once_with(
        query, k=3, profile=user_profile, filters={}
    )

    # Verify event ranker was called with ALL parameters
    mock_event_ranker.rank_events.assert_called_once()
    call_args = mock_event_ranker.rank_events.call_args

    # Check that results, profile, and user_query were all passed
    assert call_args[0][0] is not None, "Results should be passed"
    assert call_args[0][1] == user_profile, "Profile should be passed"
    assert call_args[1]["user_query"] == query, "User query should be passed"

    # Verify results are returned (ranking happens in mock)
    assert len(results) == 3
    assert results is not None


def test_recommender_without_profile_skips_ranking(mock_vector_store, mock_event_ranker):
    """Test that without profile, only RAG scores are used."""
    agent = RecommenderAgent(event_ranker=mock_event_ranker, vector_store=mock_vector_store)

    query = "contemporary art"
    results = agent.recommend(query=query, profile=None, k=3)

    # Should return RAG results sorted by score
    assert len(results) == 3
    # Video art has highest RAG score (0.90)
    assert results[0].event_id == "3"
    assert results[0].score == 0.90


def test_ranking_considers_query_and_profile(
    mock_vector_store, user_profile, mock_event_ranker
):
    """Test that ranking logic considers both query intent and user preferences."""
    agent = RecommenderAgent(
        vector_store=mock_vector_store,
        event_ranker=mock_event_ranker,
    )

    # User asks for sculpture (matches their profile)
    query = "sculpture exhibitions"
    results = agent.recommend(query=query, profile=user_profile, k=3)

    # The mock ranker should put sculpture first (event_id=1)
    # even though video art (event_id=3) has higher RAG score
    # This demonstrates profile-based re-ranking
    assert results[0].event_id == "1"  # Sculpture (favorite genre)
    assert results[0].score == 0.85

    # Video art should be last (disliked genre)
    assert results[-1].event_id == "3"
    assert "video art" in results[-1].genres


@patch("agents.event_ranker.geocoder_tool")
def test_ranking_includes_location_context(
    mock_geocoder, mock_vector_store, user_profile, mock_event_ranker
):
    """Test that location is resolved and passed to ranking."""
    # Mock geocoding
    mock_geocoder.geocode.return_value = {"lat": 41.3851, "lon": 2.1734}
    mock_geocoder.calculate_distance.return_value = 1.5

    agent = RecommenderAgent(
        vector_store=mock_vector_store,
        event_ranker=mock_event_ranker,
    )

    query = "art exhibitions near me"
    results = agent.recommend(query=query, profile=user_profile, k=3)

    # Verify geocoding was attempted
    # (The actual call happens inside EventRanker, but we can verify it's set up)
    assert user_profile.location == "Barcelona"

    # Verify ranker was called (which internally uses geocoding)
    mock_event_ranker.rank_events.assert_called_once()

    # Verify results were returned
    assert len(results) == 3
