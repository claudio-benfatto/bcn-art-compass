"""
JSON-based memory storage for user profiles.

This module provides simple file-based persistence for user profiles.
For cloud deployment, this can be swapped with Firestore.
"""

import json
from pathlib import Path
from typing import Optional

from memory.models import UserProfile
from memory.storage_interface import ProfileStorage
from observability import log_info, log_memory_update


class MemoryStorage(ProfileStorage):
    """
    JSON-based storage for user profiles.

    Stores profiles in a single JSON file (memory/user_profiles.json).
    Thread-safe for local development (single process).
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize memory storage.

        Args:
            storage_path: Path to JSON file. If None, uses memory/user_profiles.json
        """
        if storage_path is None:
            storage_path = str(Path(__file__).parent.parent / "storage" / "user_profiles.json")

        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize empty file if it doesn't exist
        if not self.storage_path.exists():
            self._write_profiles({})
            log_info("memory_storage_initialized", path=str(self.storage_path), profiles=0)
        else:
            profiles = self._read_profiles()
            log_info(
                "memory_storage_loaded",
                path=str(self.storage_path),
                profiles=len(profiles),
            )

    def _read_profiles(self) -> dict[str, dict]:
        """Read all profiles from JSON file."""
        try:
            with open(self.storage_path, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            log_info("memory_storage_read_error", path=str(self.storage_path))
            return {}

    def _write_profiles(self, profiles: dict[str, dict]) -> None:
        """Write all profiles to JSON file."""
        with open(self.storage_path, "w") as f:
            json.dump(profiles, f, indent=2)

    def load_profile(self, user_id: str) -> UserProfile:
        """
        Load user profile by ID.

        Creates a new profile if user_id doesn't exist.

        Args:
            user_id: User identifier

        Returns:
            UserProfile: User profile (new or existing)
        """
        profiles = self._read_profiles()

        if user_id in profiles:
            log_info("profile_loaded", user_id=user_id, exists=True)
            return UserProfile(**profiles[user_id])
        else:
            # Create new profile
            new_profile = UserProfile(user_id=user_id)
            log_info("profile_created", user_id=user_id, exists=False)
            return new_profile

    def save_profile(self, profile: UserProfile) -> None:
        """
        Save user profile.

        Args:
            profile: UserProfile to save
        """
        profiles = self._read_profiles()
        profiles[profile.user_id] = profile.model_dump()
        self._write_profiles(profiles)

        log_memory_update(
            user_id=profile.user_id,
            operation="profile_saved",
            changes={
                "favorite_genres": len(profile.favorite_genres),
                "disliked_genres": len(profile.disliked_genres),
                "favorite_artists": len(profile.favorite_artists),
            },
        )

    def delete_profile(self, user_id: str) -> bool:
        """
        Delete user profile.

        Args:
            user_id: User identifier

        Returns:
            bool: True if profile was deleted, False if it didn't exist
        """
        profiles = self._read_profiles()

        if user_id in profiles:
            del profiles[user_id]
            self._write_profiles(profiles)
            log_info("profile_deleted", user_id=user_id)
            return True
        else:
            log_info("profile_not_found", user_id=user_id)
            return False

    def list_profiles(self) -> list[str]:
        """
        List all user IDs.

        Returns:
            list[str]: List of user IDs
        """
        profiles = self._read_profiles()
        return list(profiles.keys())

    def profile_exists(self, user_id: str) -> bool:
        """
        Check if profile exists.

        Args:
            user_id: User identifier

        Returns:
            bool: True if profile exists
        """
        profiles = self._read_profiles()
        return user_id in profiles
