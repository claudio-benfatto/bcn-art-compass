import pytest

from memory.storage import MemoryStorage
from agents.tools.profile_tools import create_profile_tools

class DummyExtractor:
    async def extract(self, text: str):
        # Simple deterministic extraction for tests
        return {
            "favorite_genres": ["Contemporary Art", "sculpture", "sculpture"],
            "disliked_genres": ["VIDEO art"],
            "favorite_artists": ["Picasso"],
            "location": "Barcelona",
        }

class ErrorExtractor:
    async def extract(self, text: str):
        raise RuntimeError("boom")

@pytest.mark.asyncio
async def test_extract_preferences_diff_added():
    import uuid
    storage = MemoryStorage()
    get_profile, update_profile, extract_prefs = create_profile_tools(
        storage=storage, preference_extractor=DummyExtractor()
    )

    user_id = f"test_user_diff_added_{uuid.uuid4().hex[:8]}"
    result = await extract_prefs(user_id, "I love contemporary art and sculpture")

    assert "profile" in result and "updated" in result
    updated = result["updated"]
    # Normalization: lowercase + dedupe
    assert set(updated["favorite_genres_added"]) == {"contemporary art", "sculpture"}
    assert updated["disliked_genres_added"] == ["video art"]
    assert updated["favorite_artists_added"] == ["picasso"]
    assert updated["location_changed"] is True

    profile = result["profile"]
    assert "contemporary art" in profile["favorite_genres"]
    assert "video art" in profile["disliked_genres"]
    assert profile["location"] == "Barcelona"

@pytest.mark.asyncio
async def test_extract_preferences_error_path():
    storage = MemoryStorage()
    get_profile, update_profile, extract_prefs = create_profile_tools(
        storage=storage, preference_extractor=ErrorExtractor()
    )

    result = await extract_prefs("user999", "Anything")
    assert "error" in result
    assert result["updated"] == {}
    assert "profile" in result
    # Profile should be created but empty prefs
    profile = result["profile"]
    assert profile["favorite_genres"] == []
    assert profile["disliked_genres"] == []
    assert profile["favorite_artists"] == []
