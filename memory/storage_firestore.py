"""
Firestore-based storage backend for user profiles.

Drop-in replacement for JSON storage that works in cloud environments.
Maintains identical API to MemoryStorage for seamless switching.
"""

import os
from typing import Optional

from google.cloud import firestore

from memory.models import UserProfile
from observability import log_info


class FirestoreStorage:
    """
    Firestore-based profile storage.
    
    Identical API to MemoryStorage but persists to Firestore.
    Auto-creates collection and manages documents.
    """

    def __init__(
        self,
        collection_name: str = "user_profiles",
        project_id: Optional[str] = None,
    ):
        """
        Initialize Firestore storage.

        Args:
            collection_name: Firestore collection name
            project_id: GCP project ID. If None, uses GOOGLE_CLOUD_PROJECT env var
        """
        self.collection_name = collection_name
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        
        # Initialize Firestore client
        self.db = firestore.Client(project=self.project_id)
        self.collection = self.db.collection(collection_name)
        
        log_info(
            "firestore_storage_initialized",
            collection=collection_name,
            project=self.project_id,
        )

    def load_profile(self, user_id: str) -> UserProfile:
        """
        Load user profile from Firestore.

        Creates a new profile if user doesn't exist.

        Args:
            user_id: User identifier

        Returns:
            UserProfile: User profile
        """
        doc_ref = self.collection.document(user_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            profile = UserProfile(**data)
            log_info("profile_loaded", user_id=user_id, exists=True, source="firestore")
            return profile
        else:
            # Create new profile
            profile = UserProfile(user_id=user_id)
            self.save_profile(profile)
            log_info("profile_created", user_id=user_id, source="firestore")
            return profile

    def save_profile(self, profile: UserProfile) -> None:
        """
        Save user profile to Firestore.

        Args:
            profile: UserProfile to save
        """
        doc_ref = self.collection.document(profile.user_id)
        
        # Convert to dict for Firestore
        profile_dict = profile.model_dump()
        
        # Save to Firestore
        doc_ref.set(profile_dict)
        
        log_info(
            "profile_saved",
            user_id=profile.user_id,
            source="firestore",
            changes={
                "favorite_genres": len(profile.favorite_genres),
                "disliked_genres": len(profile.disliked_genres),
                "favorite_artists": len(profile.favorite_artists),
            },
        )

    def delete_profile(self, user_id: str) -> None:
        """
        Delete user profile from Firestore.

        Args:
            user_id: User identifier
        """
        doc_ref = self.collection.document(user_id)
        doc_ref.delete()
        log_info("profile_deleted", user_id=user_id, source="firestore")

    def list_profiles(self) -> list[str]:
        """
        List all user IDs in Firestore.

        Returns:
            list[str]: List of user IDs
        """
        docs = self.collection.stream()
        user_ids = [doc.id for doc in docs]
        log_info("profiles_listed", count=len(user_ids), source="firestore")
        return user_ids
