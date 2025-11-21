"""
Tests for Firestore storage backend.

Uses mocked Firestore client to test profile storage operations.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from memory.storage_firestore import FirestoreStorage
from memory.models import UserProfile


@pytest.fixture
def mock_firestore_client():
    """Create a mocked Firestore client."""
    with patch('memory.storage_firestore.firestore.Client') as mock_client_class:
        # Create mock client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Create mock collection
        mock_collection = MagicMock()
        mock_client.collection.return_value = mock_collection
        
        yield mock_client, mock_collection


def test_firestore_storage_initialization(mock_firestore_client):
    """Test FirestoreStorage initialization."""
    mock_client, mock_collection = mock_firestore_client
    
    storage = FirestoreStorage(
        collection_name="test_profiles",
        project_id="test-project",
    )
    
    assert storage.collection_name == "test_profiles"
    assert storage.project_id == "test-project"
    mock_client.collection.assert_called_once_with("test_profiles")


def test_load_profile_existing(mock_firestore_client):
    """Test loading an existing profile."""
    mock_client, mock_collection = mock_firestore_client
    
    # Mock document exists
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "user_id": "user123",
        "location": "Barcelona",
        "favorite_genres": ["contemporary art"],
        "disliked_genres": [],
        "favorite_artists": ["Picasso"],
        "preferred_distance_km": 10,
    }
    
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_collection.document.return_value = mock_doc_ref
    
    storage = FirestoreStorage(project_id="test-project")
    profile = storage.load_profile("user123")
    
    assert profile.user_id == "user123"
    assert profile.location == "Barcelona"
    assert profile.favorite_genres == ["contemporary art"]
    assert profile.favorite_artists == ["Picasso"]
    mock_collection.document.assert_called_with("user123")


def test_load_profile_new_user(mock_firestore_client):
    """Test loading a profile for a new user (creates new profile)."""
    mock_client, mock_collection = mock_firestore_client
    
    # Mock document does not exist
    mock_doc = MagicMock()
    mock_doc.exists = False
    
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_collection.document.return_value = mock_doc_ref
    
    storage = FirestoreStorage(project_id="test-project")
    profile = storage.load_profile("newuser")
    
    assert profile.user_id == "newuser"
    assert profile.location is None
    assert profile.favorite_genres == []
    # Verify save was called to create the profile
    mock_doc_ref.set.assert_called_once()


def test_save_profile(mock_firestore_client):
    """Test saving a profile."""
    mock_client, mock_collection = mock_firestore_client
    
    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    
    storage = FirestoreStorage(project_id="test-project")
    
    profile = UserProfile(
        user_id="user123",
        location="Barcelona",
        favorite_genres=["sculpture"],
        disliked_genres=["video art"],
        favorite_artists=["Gaudí"],
        preferred_distance_km=15,
    )
    
    storage.save_profile(profile)
    
    mock_collection.document.assert_called_with("user123")
    mock_doc_ref.set.assert_called_once()
    
    # Verify the data passed to set()
    call_args = mock_doc_ref.set.call_args
    saved_data = call_args[0][0]
    
    assert saved_data["user_id"] == "user123"
    assert saved_data["location"] == "Barcelona"
    assert saved_data["favorite_genres"] == ["sculpture"]
    assert saved_data["disliked_genres"] == ["video art"]
    assert saved_data["favorite_artists"] == ["Gaudí"]
    assert saved_data["preferred_distance_km"] == 15


def test_delete_profile(mock_firestore_client):
    """Test deleting a profile."""
    mock_client, mock_collection = mock_firestore_client
    
    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    
    storage = FirestoreStorage(project_id="test-project")
    storage.delete_profile("user123")
    
    mock_collection.document.assert_called_with("user123")
    mock_doc_ref.delete.assert_called_once()


def test_list_profiles(mock_firestore_client):
    """Test listing all profiles."""
    mock_client, mock_collection = mock_firestore_client
    
    # Mock document stream
    mock_doc1 = MagicMock()
    mock_doc1.id = "user1"
    
    mock_doc2 = MagicMock()
    mock_doc2.id = "user2"
    
    mock_doc3 = MagicMock()
    mock_doc3.id = "user3"
    
    mock_collection.stream.return_value = [mock_doc1, mock_doc2, mock_doc3]
    
    storage = FirestoreStorage(project_id="test-project")
    user_ids = storage.list_profiles()
    
    assert user_ids == ["user1", "user2", "user3"]
    mock_collection.stream.assert_called_once()


def test_list_profiles_empty(mock_firestore_client):
    """Test listing profiles when collection is empty."""
    mock_client, mock_collection = mock_firestore_client
    
    mock_collection.stream.return_value = []
    
    storage = FirestoreStorage(project_id="test-project")
    user_ids = storage.list_profiles()
    
    assert user_ids == []


def test_firestore_storage_with_env_var(mock_firestore_client):
    """Test FirestoreStorage uses GOOGLE_CLOUD_PROJECT env var."""
    mock_client, mock_collection = mock_firestore_client
    
    with patch.dict('os.environ', {'GOOGLE_CLOUD_PROJECT': 'env-project'}):
        storage = FirestoreStorage()
        assert storage.project_id == "env-project"


def test_save_and_load_round_trip(mock_firestore_client):
    """Test saving and loading a profile (round trip)."""
    mock_client, mock_collection = mock_firestore_client
    
    # Setup mocks
    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    
    storage = FirestoreStorage(project_id="test-project")
    
    # Create and save profile
    original_profile = UserProfile(
        user_id="test_user",
        location="Madrid",
        favorite_genres=["modern art", "sculpture"],
        disliked_genres=["abstract"],
        favorite_artists=["Dalí", "Miró"],
        preferred_distance_km=20,
    )
    
    storage.save_profile(original_profile)
    
    # Mock the load to return what was saved
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = original_profile.model_dump()
    mock_doc_ref.get.return_value = mock_doc
    
    # Load profile
    loaded_profile = storage.load_profile("test_user")
    
    # Verify data matches
    assert loaded_profile.user_id == original_profile.user_id
    assert loaded_profile.location == original_profile.location
    assert loaded_profile.favorite_genres == original_profile.favorite_genres
    assert loaded_profile.disliked_genres == original_profile.disliked_genres
    assert loaded_profile.favorite_artists == original_profile.favorite_artists
    assert loaded_profile.preferred_distance_km == original_profile.preferred_distance_km
