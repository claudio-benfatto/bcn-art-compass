"""Tests for update_profile_tool removal capability and diff schema."""

from agents.tools.profile_tools import create_profile_tools
from memory.storage import MemoryStorage


def setup_tools():
    storage = MemoryStorage()
    get_profile, update_profile, extract_preferences = create_profile_tools(storage=storage)
    return storage, get_profile, update_profile, extract_preferences


def test_update_profile_tool_removal_success():
    storage, get_profile, update_profile, _ = setup_tools()

    # Add initial preferences
    add_result = update_profile(
        "user_remove",
        favorite_genres=["sculpture", "painting"],
        disliked_genres=["video art"],
        favorite_artists=["Picasso"],
    )
    assert "profile" in add_result
    assert set(add_result["profile"]["favorite_genres"]) == {"sculpture", "painting"}

    # Remove some
    removal_result = update_profile(
        "user_remove",
        remove_favorite_genres=["painting"],
        remove_disliked_genres=["video art"],
        remove_favorite_artists=["Picasso"],
    )

    updated = removal_result["updated"]
    assert updated["favorite_genres_removed"] == ["painting"]
    assert updated["disliked_genres_removed"] == ["video art"]
    assert updated["favorite_artists_removed"] == ["Picasso"]
    assert updated["favorite_genres_not_found"] == []
    assert updated["disliked_genres_not_found"] == []
    assert updated["favorite_artists_not_found"] == []

    profile = removal_result["profile"]
    assert profile["favorite_genres"] == ["sculpture"]
    assert profile["disliked_genres"] == []
    assert profile["favorite_artists"] == []


def test_update_profile_tool_removal_not_found():
    storage, get_profile, update_profile, _ = setup_tools()

    # Ensure profile exists but no preferences yet
    initial = get_profile("user_not_found")
    assert initial["favorite_genres"] == []

    # Attempt to remove non-existent items
    removal_result = update_profile(
        "user_not_found",
        remove_favorite_genres=["nonexistent"],
        remove_disliked_genres=["missing_dislike"],
        remove_favorite_artists=["unknown artist"],
    )

    updated = removal_result["updated"]
    assert updated["favorite_genres_removed"] == []
    assert updated["favorite_genres_not_found"] == ["nonexistent"]
    assert updated["disliked_genres_removed"] == []
    assert updated["disliked_genres_not_found"] == ["missing_dislike"]
    assert updated["favorite_artists_removed"] == []
    assert updated["favorite_artists_not_found"] == ["unknown artist"]

    profile = removal_result["profile"]
    assert profile["favorite_genres"] == []
    assert profile["disliked_genres"] == []
    assert profile["favorite_artists"] == []
