"""
Tests for Milestone 3: Preference extraction from natural language.

Tests the ProfileAgent.extract_preferences() method with mocked LLM responses.
"""

import json
from unittest.mock import MagicMock

import pytest

from agents.profile_agent import ProfileAgent
from memory.storage import MemoryStorage


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage for testing."""
    storage_path = tmp_path / "test_profiles.json"
    return MemoryStorage(str(storage_path))


@pytest.fixture
def profile_agent(temp_storage):
    """Create a ProfileAgent with temporary storage for testing.
    
    Tests will mock the LLM client, so we just need the agent structure.
    """
    agent = ProfileAgent(storage=temp_storage, use_local_llm=False)
    # Override to allow mocking - tests will inject mock_gemini_model
    agent.llm_type = "gemini"  # Ensure LLM path is taken, not rule-based
    agent.model = "gemini-1.5-flash"  # Set a model name
    return agent


@pytest.fixture
def mock_gemini_model():
    """Create a mock Gemini client."""
    client = MagicMock()
    return client


def create_gemini_response(favorite_genres=None, disliked_genres=None, favorite_artists=None, location=None):
    """
    Helper to create a mock Gemini API response.

    Args:
        favorite_genres: List of favorite genres
        disliked_genres: List of disliked genres
        favorite_artists: List of favorite artists
        location: Location string

    Returns:
        Mock response object
    """
    response_data = {
        "favorite_genres": favorite_genres or [],
        "disliked_genres": disliked_genres or [],
        "favorite_artists": favorite_artists or [],
        "location": location,
    }
    response = MagicMock()
    response.text = json.dumps(response_data)
    return response


@pytest.mark.asyncio
async def test_extract_simple_dislike(profile_agent, mock_gemini_model):
    """Test extracting a simple dislike statement."""
    # Mock the model response
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        disliked_genres=["video art"]
    )

    # Replace the agent's model
    profile_agent.client = mock_gemini_model

    # Extract preferences
    profile = await profile_agent.extract_preferences("test_user", "I don't like video art")

    # Verify
    assert "video art" in profile.disliked_genres
    assert len(profile.favorite_genres) == 0
    assert len(profile.favorite_artists) == 0


@pytest.mark.asyncio
async def test_extract_simple_like(profile_agent, mock_gemini_model):
    """Test extracting a simple like statement."""
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_genres=["contemporary sculpture"]
    )

    profile_agent.client = mock_gemini_model

    profile = await profile_agent.extract_preferences("test_user", "I love contemporary sculpture")

    assert "contemporary sculpture" in profile.favorite_genres
    assert len(profile.disliked_genres) == 0


@pytest.mark.asyncio
async def test_extract_multiple_preferences(profile_agent, mock_gemini_model):
    """Test extracting multiple preferences in one statement."""
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_genres=["contemporary art", "sculpture"],
        favorite_artists=["Picasso", "Miró"]
    )

    profile_agent.client = mock_gemini_model

    profile = await profile_agent.extract_preferences(
        "test_user",
        "I love contemporary art and sculpture, especially Picasso and Miró"
    )

    assert "contemporary art" in profile.favorite_genres
    assert "sculpture" in profile.favorite_genres
    assert "Picasso" in profile.favorite_artists
    assert "Miró" in profile.favorite_artists


@pytest.mark.asyncio
async def test_extract_artist_mention(profile_agent, mock_gemini_model):
    """Test extracting favorite artist mentions."""
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_artists=["Antoni Tàpies"]
    )

    profile_agent.client = mock_gemini_model

    profile = await profile_agent.extract_preferences(
        "test_user",
        "My favorite artist is Antoni Tàpies"
    )

    assert "Antoni Tàpies" in profile.favorite_artists


@pytest.mark.asyncio
async def test_extract_location(profile_agent, mock_gemini_model):
    """Test extracting location information."""
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        location="Gràcia, Barcelona"
    )

    profile_agent.client = mock_gemini_model

    profile = await profile_agent.extract_preferences(
        "test_user",
        "I live in the Gràcia neighborhood"
    )

    assert profile.location == "Gràcia, Barcelona"


@pytest.mark.asyncio
async def test_extract_with_markdown_cleanup(profile_agent, mock_gemini_model):
    """Test that markdown code blocks are properly cleaned up."""
    # Mock response with markdown code block
    mock_response = MagicMock()
    mock_response.text = """```json
{
  "favorite_genres": ["painting"],
  "disliked_genres": [],
  "favorite_artists": [],
  "location": null
}
```"""
    mock_gemini_model.models.generate_content.return_value = mock_response

    profile_agent.client = mock_gemini_model

    profile = await profile_agent.extract_preferences("test_user", "I like painting")

    assert "painting" in profile.favorite_genres


@pytest.mark.asyncio
async def test_extract_handles_error_gracefully(profile_agent, mock_gemini_model):
    """Test that errors during extraction are handled gracefully."""
    # Mock an error
    mock_gemini_model.generate_content.side_effect = Exception("API error")

    profile_agent.client = mock_gemini_model

    # Should return existing profile without crashing
    profile = await profile_agent.extract_preferences("test_user", "I like art")

    # Profile should exist but have no changes
    assert profile is not None


@pytest.mark.asyncio
async def test_extract_invalid_json_fallback(profile_agent, mock_gemini_model):
    """Test fallback when LLM returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON"
    mock_gemini_model.models.generate_content.return_value = mock_response

    profile_agent.client = mock_gemini_model

    # Should return existing profile without crashing
    profile = await profile_agent.extract_preferences("test_user", "I like art")

    assert profile is not None


@pytest.mark.asyncio
async def test_extract_updates_existing_profile(profile_agent, mock_gemini_model):
    """Test that extraction updates an existing profile."""
    # Create initial profile with one preference
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_genres=["painting"]
    )
    profile_agent.client = mock_gemini_model

    profile1 = await profile_agent.extract_preferences("test_user", "I like painting")
    assert "painting" in profile1.favorite_genres

    # Add another preference
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_genres=["sculpture"]
    )

    profile2 = await profile_agent.extract_preferences("test_user", "I also like sculpture")

    # Both preferences should be present
    assert "painting" in profile2.favorite_genres
    assert "sculpture" in profile2.favorite_genres


@pytest.mark.asyncio
async def test_extract_persistence(profile_agent, mock_gemini_model):
    """Test that extracted preferences are persisted to storage."""
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_genres=["abstract art"]
    )
    profile_agent.client = mock_gemini_model

    await profile_agent.extract_preferences("test_user", "I love abstract art")

    # Load profile again to verify persistence
    loaded_profile = profile_agent.load_profile("test_user")
    assert "abstract art" in loaded_profile.favorite_genres


@pytest.mark.asyncio
async def test_extract_mixed_likes_and_dislikes(profile_agent, mock_gemini_model):
    """Test extracting both likes and dislikes in one statement."""
    mock_gemini_model.models.generate_content.return_value = create_gemini_response(
        favorite_genres=["painting"],
        disliked_genres=["video art", "performance art"]
    )
    profile_agent.client = mock_gemini_model

    profile = await profile_agent.extract_preferences(
        "test_user",
        "I like painting but I don't like video art or performance art"
    )

    assert "painting" in profile.favorite_genres
    assert "video art" in profile.disliked_genres
    assert "performance art" in profile.disliked_genres
