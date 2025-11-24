"""
Storage interface for user profiles.

Defines the contract that all storage backends must implement.
Enables seamless switching between JSON, Firestore, or other backends.
"""

from typing import Protocol, runtime_checkable

from memory.models import UserProfile


@runtime_checkable
class ProfileStorage(Protocol):
    """
    Protocol defining the interface for profile storage backends.
    
    All storage implementations (MemoryStorage, FirestoreStorage, etc.)
    must implement these methods to be used interchangeably.
    """

    def load_profile(self, user_id: str) -> UserProfile:
        """
        Load user profile by ID.

        Creates a new profile if user_id doesn't exist.

        Args:
            user_id: User identifier

        Returns:
            UserProfile: User profile (new or existing)
        """
        ...

    def save_profile(self, profile: UserProfile) -> None:
        """
        Save user profile.

        Args:
            profile: UserProfile to save
        """
        ...

    def delete_profile(self, user_id: str) -> bool:
        """
        Delete user profile.

        Args:
            user_id: User identifier

        Returns:
            bool: True if profile was deleted, False if it didn't exist
        """
        ...

    def list_profiles(self) -> list[str]:
        """
        List all user IDs.

        Returns:
            list[str]: List of user IDs
        """
        ...

    def profile_exists(self, user_id: str) -> bool:
        """
        Check if profile exists.

        Args:
            user_id: User identifier

        Returns:
            bool: True if profile exists
        """
        ...
