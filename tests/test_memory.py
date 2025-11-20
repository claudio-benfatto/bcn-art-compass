"""
Unit tests for memory storage system.
"""

import json
import os
import tempfile

import pytest

from memory.models import UserProfile
from memory.storage import MemoryStorage


@pytest.fixture
def temp_storage():
    """Create a temporary storage file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        temp_path = f.name

    storage = MemoryStorage(storage_path=temp_path)
    yield storage

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_create_new_profile(temp_storage):
    """Test creating a new user profile."""
    profile = temp_storage.load_profile("user123")

    assert profile.user_id == "user123"
    assert profile.favorite_genres == []
    assert profile.disliked_genres == []
    assert profile.favorite_artists == []
    assert profile.location is None


def test_save_and_load_profile(temp_storage):
    """Test saving and loading a profile."""
    # Create and modify profile
    profile = temp_storage.load_profile("user456")
    profile.add_favorite_genre("sculpture")
    profile.add_favorite_genre("contemporary art")
    profile.add_favorite_artist("Picasso")
    profile.location = "Barcelona"

    # Save it
    temp_storage.save_profile(profile)

    # Load it again
    loaded_profile = temp_storage.load_profile("user456")

    assert loaded_profile.user_id == "user456"
    assert "sculpture" in loaded_profile.favorite_genres
    assert "contemporary art" in loaded_profile.favorite_genres
    assert "Picasso" in loaded_profile.favorite_artists
    assert loaded_profile.location == "Barcelona"


def test_update_existing_profile(temp_storage):
    """Test updating an existing profile."""
    # Create initial profile
    profile = temp_storage.load_profile("user789")
    profile.add_favorite_genre("painting")
    temp_storage.save_profile(profile)

    # Load and update
    profile = temp_storage.load_profile("user789")
    profile.add_favorite_genre("digital art")
    profile.add_disliked_genre("video art")
    temp_storage.save_profile(profile)

    # Verify updates
    loaded_profile = temp_storage.load_profile("user789")
    assert "painting" in loaded_profile.favorite_genres
    assert "digital art" in loaded_profile.favorite_genres
    assert "video art" in loaded_profile.disliked_genres


def test_delete_profile(temp_storage):
    """Test deleting a profile."""
    # Create profile
    profile = temp_storage.load_profile("user_to_delete")
    profile.add_favorite_genre("test_genre")
    temp_storage.save_profile(profile)

    # Verify it exists
    assert temp_storage.profile_exists("user_to_delete")

    # Delete it
    result = temp_storage.delete_profile("user_to_delete")
    assert result is True

    # Verify it's gone
    assert not temp_storage.profile_exists("user_to_delete")

    # Try deleting non-existent profile
    result = temp_storage.delete_profile("non_existent")
    assert result is False


def test_list_profiles(temp_storage):
    """Test listing all profiles."""
    # Create multiple profiles
    for i in range(3):
        profile = temp_storage.load_profile(f"user{i}")
        profile.add_favorite_genre(f"genre{i}")
        temp_storage.save_profile(profile)

    # List profiles
    user_ids = temp_storage.list_profiles()
    assert len(user_ids) == 3
    assert "user0" in user_ids
    assert "user1" in user_ids
    assert "user2" in user_ids


def test_profile_model_add_methods():
    """Test UserProfile add/remove methods."""
    profile = UserProfile(user_id="test_user")

    # Add favorites
    profile.add_favorite_genre("sculpture")
    profile.add_favorite_genre("sculpture")  # Duplicate, should not be added
    assert profile.favorite_genres == ["sculpture"]

    profile.add_favorite_artist("Picasso")
    assert profile.favorite_artists == ["Picasso"]

    # Add dislikes
    profile.add_disliked_genre("video art")
    assert profile.disliked_genres == ["video art"]


def test_profile_model_remove_methods():
    """Test UserProfile remove methods."""
    profile = UserProfile(user_id="test_user")

    # Add some preferences
    profile.add_favorite_genre("sculpture")
    profile.add_favorite_genre("painting")
    profile.add_favorite_artist("Picasso")
    profile.add_disliked_genre("video art")

    # Remove them
    profile.remove_favorite_genre("sculpture")
    assert "sculpture" not in profile.favorite_genres
    assert "painting" in profile.favorite_genres

    profile.remove_favorite_artist("Picasso")
    assert profile.favorite_artists == []

    profile.remove_disliked_genre("video art")
    assert profile.disliked_genres == []


def test_profile_timestamps():
    """Test that timestamps are set and updated."""
    profile = UserProfile(user_id="test_user")

    created_at = profile.created_at
    updated_at = profile.updated_at

    assert created_at is not None
    assert updated_at is not None

    # Make a change
    profile.add_favorite_genre("test_genre")

    # Updated timestamp should change
    assert profile.updated_at != updated_at
    assert profile.created_at == created_at  # Created timestamp should not change


def test_profile_persistence_format(temp_storage):
    """Test that profiles are persisted in correct JSON format."""
    # Create and save profile
    profile = temp_storage.load_profile("format_test")
    profile.add_favorite_genre("sculpture")
    profile.location = "Barcelona"
    temp_storage.save_profile(profile)

    # Read raw JSON
    with open(temp_storage.storage_path, "r") as f:
        data = json.load(f)

    assert "format_test" in data
    user_data = data["format_test"]
    assert user_data["user_id"] == "format_test"
    assert "sculpture" in user_data["favorite_genres"]
    assert user_data["location"] == "Barcelona"
    assert "created_at" in user_data
    assert "updated_at" in user_data
