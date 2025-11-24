"""
Integration test for Milestone 3: End-to-end preference flow.

Tests the complete flow:
1. User expresses preference
2. Profile is updated
3. Subsequent recommendations reflect the preference
"""

from unittest.mock import MagicMock

import pytest

from agents.orchestrator import OrchestratorAgent
from agents.profile_agent import ProfileAgent
from memory.storage import MemoryStorage


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage for testing."""
    storage_path = tmp_path / "test_profiles.json"
    return MemoryStorage(str(storage_path))


@pytest.fixture
def profile_agent(temp_storage):
    """Create a ProfileAgent with temporary storage."""
    return ProfileAgent(storage=temp_storage)


@pytest.fixture
def recommender_agent():
    """Create a RecommenderAgent for testing."""
    from agents.recommender_agent import RecommenderAgent
    from rag.vector_store import VectorStore

    # Use local embeddings to avoid API costs
    vector_store = VectorStore(use_local_embeddings=True)
    return RecommenderAgent(vector_store=vector_store)


@pytest.fixture
def orchestrator(recommender_agent, profile_agent):
    """Create an OrchestratorAgent with test components."""
    return OrchestratorAgent(
        recommender_agent=recommender_agent,
        profile_agent=profile_agent,
    )


@pytest.mark.asyncio
async def test_preference_flow_end_to_end(orchestrator, temp_storage):
    """
    Test full flow: express preference → profile updated → recommendations reflect preference.
    """
    user_id = "integration_test_user"

    # Mock the Gemini model for preference extraction
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{"favorite_genres": [], "disliked_genres": ["video art"], '
        '"favorite_artists": [], "location": null}'
    )
    mock_model.generate_content.return_value = mock_response
    orchestrator.profile_agent.model = mock_model

    # Step 1: User expresses dislike for video art
    response = await orchestrator.process_query("I don't like video art", user_id=user_id)

    # Verify response acknowledges the preference
    assert "updated your preferences" in response.lower()
    assert "disliked genre" in response.lower()

    # Step 2: Verify profile was updated
    profile = orchestrator.profile_agent.load_profile(user_id)
    assert "video art" in profile.disliked_genres
    assert len(profile.disliked_genres) == 1
    assert len(profile.favorite_genres) == 0

    # Step 3: Verify persistence (reload from storage)
    reloaded_profile = temp_storage.load_profile(user_id)
    assert "video art" in reloaded_profile.disliked_genres

    # Step 4: Make a recommendation query
    # The profile should be applied to RAG scoring
    rec_response = await orchestrator.process_query("Show me contemporary art exhibitions", user_id=user_id)

    # Response should contain recommendations
    assert "I found" in rec_response or "events" in rec_response.lower()

    # Note: We can't easily verify that video art events are penalized without
    # having actual video art events in the test data, but we've verified:
    # 1. Profile was updated
    # 2. Profile persisted
    # 3. Recommendations query works
    # The RAG scoring logic is tested separately in test_rag.py


@pytest.mark.asyncio
async def test_multiple_preference_updates(orchestrator):
    """Test that multiple preference updates accumulate correctly."""
    user_id = "multi_pref_user"

    # Mock the Gemini model
    mock_model = MagicMock()
    orchestrator.profile_agent.model = mock_model

    # First preference: like sculpture
    mock_response1 = MagicMock()
    mock_response1.text = (
        '{"favorite_genres": ["sculpture"], "disliked_genres": [], '
        '"favorite_artists": [], "location": null}'
    )
    mock_model.generate_content.return_value = mock_response1

    response1 = await orchestrator.process_query("I love sculpture", user_id=user_id)
    assert "updated your preferences" in response1.lower()

    # Second preference: dislike performance art
    mock_response2 = MagicMock()
    mock_response2.text = (
        '{"favorite_genres": [], "disliked_genres": ["performance art"], '
        '"favorite_artists": [], "location": null}'
    )
    mock_model.generate_content.return_value = mock_response2

    response2 = await orchestrator.process_query("I don't like performance art", user_id=user_id)
    assert "updated your preferences" in response2.lower()

    # Verify both preferences are present
    profile = orchestrator.profile_agent.load_profile(user_id)
    assert "sculpture" in profile.favorite_genres
    assert "performance art" in profile.disliked_genres
    assert len(profile.favorite_genres) == 1
    assert len(profile.disliked_genres) == 1


@pytest.mark.asyncio
async def test_intent_detection_routing(orchestrator):
    """Test that intent detection routes queries correctly."""
    user_id = "intent_test_user"

    # Mock the Gemini model
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{"favorite_genres": ["painting"], "disliked_genres": [], '
        '"favorite_artists": [], "location": null}'
    )
    mock_model.generate_content.return_value = mock_response
    orchestrator.profile_agent.model = mock_model

    # Test 1: Preference update intent
    response1 = await orchestrator.process_query("I like painting", user_id=user_id)
    assert "updated your preferences" in response1.lower()

    # Test 2: Recommendation intent
    response2 = await orchestrator.process_query("Show me art exhibitions", user_id=user_id)
    assert ("I found" in response2 or "events" in response2.lower() or "couldn't find" in response2.lower())

    # Test 3: General/fallback intent
    response3 = await orchestrator.process_query("Hello", user_id=user_id)
    assert "help you discover" in response3.lower() or "try asking" in response3.lower()


@pytest.mark.asyncio
async def test_preference_affects_recommendations(orchestrator):
    """
    Test that preferences actually affect recommendation scores.

    This test verifies the integration between ProfileAgent and VectorStore.
    """
    user_id = "scoring_test_user"

    # Mock the Gemini model
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{"favorite_genres": ["contemporary art"], "disliked_genres": [], '
        '"favorite_artists": [], "location": null}'
    )
    mock_model.generate_content.return_value = mock_response
    orchestrator.profile_agent.model = mock_model

    # Add preference
    await orchestrator.process_query("I love contemporary art", user_id=user_id)

    # Get recommendations
    # This should trigger RAG search with profile-based scoring
    response = await orchestrator.process_query("Find me art events", user_id=user_id)

    # Verify we got a response
    assert response is not None
    assert len(response) > 0

    # The actual scoring boost is tested in test_rag.py,
    # here we just verify the integration works end-to-end
