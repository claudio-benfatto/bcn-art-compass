"""
Tests for ProfileStorage interface conformance.

Validates that both MemoryStorage and FirestoreStorage implement
the ProfileStorage protocol correctly and can be used interchangeably.
"""

from unittest.mock import MagicMock, patch

import pytest

from memory.models import UserProfile
from memory.storage import MemoryStorage
from memory.storage_firestore import FirestoreStorage
from memory.storage_interface import ProfileStorage


def test_memory_storage_implements_interface(tmp_path):
    """Test that MemoryStorage conforms to ProfileStorage protocol."""
    storage_path = tmp_path / "test_profiles.json"
    storage = MemoryStorage(str(storage_path))

    # Test all interface methods exist and work
    profile = storage.load_profile("test_user")
    assert isinstance(profile, UserProfile)
    assert profile.user_id == "test_user"

    storage.save_profile(profile)
    assert storage.profile_exists("test_user")

    user_ids = storage.list_profiles()
    assert "test_user" in user_ids

    result = storage.delete_profile("test_user")
    assert result is True
    assert not storage.profile_exists("test_user")


@patch("memory.storage_firestore.firestore.Client")
def test_firestore_storage_implements_interface(mock_firestore):
    """Test that FirestoreStorage conforms to ProfileStorage protocol."""
    # Mock Firestore client
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection
    mock_firestore.return_value = mock_client

    storage = FirestoreStorage(project_id="test-project")

    # Test load_profile (new user)
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_collection.document.return_value = mock_doc_ref

    profile = storage.load_profile("test_user")
    assert isinstance(profile, UserProfile)
    assert profile.user_id == "test_user"

    # Test save_profile
    storage.save_profile(profile)
    mock_doc_ref.set.assert_called()

    # Test profile_exists
    mock_doc.exists = True
    exists = storage.profile_exists("test_user")
    assert exists is True

    # Test list_profiles
    mock_doc1 = MagicMock()
    mock_doc1.id = "user1"
    mock_collection.stream.return_value = [mock_doc1]
    user_ids = storage.list_profiles()
    assert isinstance(user_ids, list)

    # Test delete_profile
    result = storage.delete_profile("test_user")
    assert result is True


def test_storage_interchangeability(tmp_path):
    """Test that storage implementations can be used interchangeably."""

    def work_with_storage(storage: ProfileStorage) -> UserProfile:
        """Function that works with any ProfileStorage implementation."""
        # Load or create profile
        profile = storage.load_profile("test_user")

        # Modify profile
        profile.add_favorite_genre("contemporary art")

        # Save profile
        storage.save_profile(profile)

        # Verify it exists
        assert storage.profile_exists("test_user")

        return profile

    # Test with MemoryStorage
    storage_path = tmp_path / "test_profiles.json"
    memory_storage = MemoryStorage(str(storage_path))
    profile1 = work_with_storage(memory_storage)
    assert "contemporary art" in profile1.favorite_genres

    # Test with FirestoreStorage (mocked)
    with patch("memory.storage_firestore.firestore.Client") as mock_firestore:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collection.return_value = mock_collection
        mock_firestore.return_value = mock_client

        # Mock for load_profile (new user)
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        firestore_storage = FirestoreStorage(project_id="test-project")

        # After save, profile should exist
        def set_exists_true(*args, **kwargs):
            mock_doc.exists = True

        mock_doc_ref.set.side_effect = set_exists_true

        profile2 = work_with_storage(firestore_storage)
        assert "contemporary art" in profile2.favorite_genres


def test_protocol_type_checking():
    """Test that ProfileStorage can be used as a type hint."""
    
    def get_user_profile(storage: ProfileStorage, user_id: str) -> UserProfile:
        """Type-annotated function accepting any storage implementation."""
        return storage.load_profile(user_id)
    
    # This function should accept both implementations
    # (This is a compile-time check, but we can verify runtime behavior)
    storage_path = "/tmp/test.json"
    memory_storage = MemoryStorage(storage_path)
    
    profile = get_user_profile(memory_storage, "test_user")
    assert isinstance(profile, UserProfile)
