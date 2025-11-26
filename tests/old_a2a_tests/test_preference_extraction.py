"""
Tests for Milestone 3: Preference extraction from natural language.

Tests the ProfileAgent.extract_preferences() method with mocked PreferenceExtractor.
"""

from typing import Dict
from unittest.mock import MagicMock

import pytest

from agents.preference_extractor import PreferenceExtractor
from agents.profile_agent import ProfileAgent
from memory.storage import MemoryStorage


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage for testing."""
    storage_path = tmp_path / "test_profiles.json"
    return MemoryStorage(str(storage_path))


class MockPreferenceExtractor(PreferenceExtractor):
    """Mock extractor for testing that returns controlled responses."""
    
    def __init__(self):
        self.mock_response: Dict = {}
    
    def set_response(self, favorite_genres=None, disliked_genres=None, favorite_artists=None, location=None):
        """Set the response that will be returned by extract()."""
        self.mock_response = {
            "favorite_genres": favorite_genres or [],
            "disliked_genres": disliked_genres or [],
            "favorite_artists": favorite_artists or [],
            "location": location,
        }
    
    async def extract(self, text: str) -> Dict:
        """Return the pre-configured mock response."""
        return self.mock_response


@pytest.fixture
def mock_extractor():
    """Create a mock preference extractor."""
    return MockPreferenceExtractor()


@pytest.fixture
def profile_agent(temp_storage, mock_extractor):
    """Create a ProfileAgent with temporary storage and mock extractor.
    
    Tests will configure mock_extractor responses.
    """
    return ProfileAgent(storage=temp_storage, preference_extractor=mock_extractor)


@pytest.mark.asyncio
async def test_extract_simple_dislike(profile_agent, mock_extractor):
    """Test extracting a simple dislike statement."""
    # Configure mock response
    mock_extractor.set_response(disliked_genres=["video art"])

    # Extract preferences
    profile = await profile_agent.extract_preferences("test_user", "I don't like video art")

    # Verify
    assert "video art" in profile.disliked_genres
    assert len(profile.favorite_genres) == 0
    assert len(profile.favorite_artists) == 0


@pytest.mark.asyncio
async def test_extract_simple_like(profile_agent, mock_extractor):
    """Test extracting a simple like statement."""
    mock_extractor.set_response(favorite_genres=["contemporary sculpture"])

    profile = await profile_agent.extract_preferences("test_user", "I love contemporary sculpture")

    assert "contemporary sculpture" in profile.favorite_genres
    assert len(profile.disliked_genres) == 0


@pytest.mark.asyncio
async def test_extract_multiple_preferences(profile_agent, mock_extractor):
    """Test extracting multiple preferences in one statement."""
    mock_extractor.set_response(
        favorite_genres=["contemporary art", "sculpture"],
        favorite_artists=["Picasso", "Miró"]
    )

    profile = await profile_agent.extract_preferences(
        "test_user",
        "I love contemporary art and sculpture, especially Picasso and Miró"
    )

    assert "contemporary art" in profile.favorite_genres
    assert "sculpture" in profile.favorite_genres
    assert "Picasso" in profile.favorite_artists
    assert "Miró" in profile.favorite_artists


@pytest.mark.asyncio
async def test_extract_artist_mention(profile_agent, mock_extractor):
    """Test extracting favorite artist mentions."""
    mock_extractor.set_response(favorite_artists=["Antoni Tàpies"])

    profile = await profile_agent.extract_preferences(
        "test_user",
        "My favorite artist is Antoni Tàpies"
    )

    assert "Antoni Tàpies" in profile.favorite_artists


@pytest.mark.asyncio
async def test_extract_location(profile_agent, mock_extractor):
    """Test extracting location information."""
    mock_extractor.set_response(location="Gràcia, Barcelona")

    profile = await profile_agent.extract_preferences(
        "test_user",
        "I live in the Gràcia neighborhood"
    )

    assert profile.location == "Gràcia, Barcelona"


@pytest.mark.asyncio
async def test_extract_with_markdown_cleanup(profile_agent, mock_extractor):
    """Test that markdown code blocks are properly cleaned up (tested in extractor)."""
    # The cleanup happens in the extractor now, so just test that extraction works
    mock_extractor.set_response(favorite_genres=["painting"])

    profile = await profile_agent.extract_preferences("test_user", "I like painting")

    assert "painting" in profile.favorite_genres


@pytest.mark.asyncio
async def test_extract_handles_error_gracefully(profile_agent):
    """Test that errors during extraction are handled gracefully."""
    # Create a mock extractor that raises an error
    error_extractor = MockPreferenceExtractor()
    
    async def raise_error(text):
        raise Exception("Extraction error")
    
    error_extractor.extract = raise_error
    profile_agent.preference_extractor = error_extractor

    # Should return existing profile without crashing
    profile = await profile_agent.extract_preferences("test_user", "I like art")

    # Profile should exist but have no changes from extraction
    assert profile is not None


@pytest.mark.asyncio
async def test_extract_invalid_json_fallback(profile_agent, mock_extractor):
    """Test fallback when extraction returns empty/invalid data."""
    # Set empty response
    mock_extractor.set_response()

    # Should return existing profile without crashing
    profile = await profile_agent.extract_preferences("test_user", "I like art")

    assert profile is not None


@pytest.mark.asyncio
async def test_extract_updates_existing_profile(profile_agent, mock_extractor):
    """Test that extraction updates an existing profile."""
    # Create initial profile with one preference
    mock_extractor.set_response(favorite_genres=["painting"])

    profile1 = await profile_agent.extract_preferences("test_user", "I like painting")
    assert "painting" in profile1.favorite_genres

    # Add another preference
    mock_extractor.set_response(favorite_genres=["sculpture"])

    profile2 = await profile_agent.extract_preferences("test_user", "I also like sculpture")

    # Both preferences should be present
    assert "painting" in profile2.favorite_genres
    assert "sculpture" in profile2.favorite_genres


@pytest.mark.asyncio
async def test_extract_persistence(profile_agent, mock_extractor):
    """Test that extracted preferences are persisted to storage."""
    mock_extractor.set_response(favorite_genres=["abstract art"])

    await profile_agent.extract_preferences("test_user", "I love abstract art")

    # Load profile again to verify persistence
    loaded_profile = profile_agent.load_profile("test_user")
    assert "abstract art" in loaded_profile.favorite_genres


@pytest.mark.asyncio
async def test_extract_mixed_likes_and_dislikes(profile_agent, mock_extractor):
    """Test extracting both likes and dislikes in one statement."""
    mock_extractor.set_response(
        favorite_genres=["painting"],
        disliked_genres=["video art", "performance art"]
    )

    profile = await profile_agent.extract_preferences(
        "test_user",
        "I like painting but I don't like video art or performance art"
    )

    assert "painting" in profile.favorite_genres
    assert "video art" in profile.disliked_genres
    assert "performance art" in profile.disliked_genres
