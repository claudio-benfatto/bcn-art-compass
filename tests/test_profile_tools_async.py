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


class IdempotentExtractor:
    async def extract(self, text: str):
        # Always return the same preferences so we can check idempotency of "apply"
        return {
            "favorite_genres": ["Sculpture"],
            "disliked_genres": ["Video Art"],
            "favorite_artists": ["Picasso"],
            "location": "Barcelona",
        }


class AddOnlyExtractor:
    async def extract(self, text: str):
        # Returns preferences that should be added on top of any existing ones
        return {
            "favorite_genres": ["Installation"],
            "disliked_genres": ["Graffiti"],
            "favorite_artists": ["Banksy"],
            "location": None,
        }

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


@pytest.mark.asyncio
async def test_extract_preferences_idempotent_on_repeat():
    """Calling extract twice with same extracted prefs should only add once."""
    storage = MemoryStorage()
    get_profile, update_profile, extract_prefs = create_profile_tools(
        storage=storage, preference_extractor=IdempotentExtractor()
    )

    user_id = "user_idempotent"

    # Ensure a clean starting profile for this user (tests may be re-run against
    # persistent JSON storage across sessions).
    storage.delete_profile(user_id)

    first = await extract_prefs(user_id, "I love sculpture and dislike video art.")
    second = await extract_prefs(user_id, "Same preferences again.")

    first_updated = first["updated"]
    second_updated = second["updated"]

    # First call adds normalized, deduped prefs
    assert set(first_updated["favorite_genres_added"]) == {"sculpture"}
    assert set(first_updated["disliked_genres_added"]) == {"video art"}
    assert set(first_updated["favorite_artists_added"]) == {"picasso"}
    assert first_updated["location_changed"] is True

    # Second call should not add duplicates
    assert second_updated["favorite_genres_added"] == []
    assert second_updated["disliked_genres_added"] == []
    assert second_updated["favorite_artists_added"] == []
    # Location is the same, so no change on second application
    assert second_updated["location_changed"] is False

    # Final stored profile should still contain the preferences once
    profile = storage.load_profile(user_id)
    assert set(profile.favorite_genres) == {"sculpture"}
    assert set(profile.disliked_genres) == {"video art"}
    assert set(profile.favorite_artists) == {"picasso"}
    assert profile.location == "Barcelona"


@pytest.mark.asyncio
async def test_extract_preferences_adds_without_removing_existing():
    """Extracted prefs should be applied on top of existing profile, not remove them."""
    storage = MemoryStorage()
    get_profile, update_profile, extract_prefs = create_profile_tools(
        storage=storage, preference_extractor=AddOnlyExtractor()
    )

    user_id = "user_add_only"

    # Ensure a clean starting profile for this user.
    storage.delete_profile(user_id)

    # Seed existing preferences via explicit update tool
    seed_result = update_profile(
        user_id,
        favorite_genres=["Sculpture"],
        disliked_genres=["Video Art"],
        favorite_artists=["Picasso"],
        location="Barcelona",
    )
    seed_profile = seed_result["profile"]
    assert set(seed_profile["favorite_genres"]) == {"sculpture"}
    assert set(seed_profile["disliked_genres"]) == {"video art"}
    assert set(seed_profile["favorite_artists"]) == {"picasso"}

    # Apply extracted preferences on top
    result = await extract_prefs(user_id, "I also like installation and dislike graffiti.")
    updated = result["updated"]
    profile = result["profile"]

    # Only the new prefs should show up as "added" in the diff
    assert set(updated["favorite_genres_added"]) == {"installation"}
    assert set(updated["disliked_genres_added"]) == {"graffiti"}
    assert set(updated["favorite_artists_added"]) == {"banksy"}
    # No location in extracted data, so no location change
    assert updated["location_changed"] is False

    # Final profile should contain both old and new preferences
    assert set(profile["favorite_genres"]) == {"sculpture", "installation"}
    assert set(profile["disliked_genres"]) == {"video art", "graffiti"}
    assert set(profile["favorite_artists"]) == {"picasso", "banksy"}
