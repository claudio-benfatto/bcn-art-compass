"""
Profile Agent - manages user preferences and long-term memory.

This agent handles loading and updating user profiles.
In Milestone 2, it's minimal (just loads profiles).
In Milestone 3, it will extract preferences from natural language.
"""

from typing import Optional

from memory.models import UserProfile
from memory.storage import MemoryStorage
from observability import log_info


class ProfileAgent:
    """
    Minimal profile agent for Milestone 2.

    Responsibilities:
    - Load user profile from storage
    - Provide access to user preferences
    - Save profile updates

    Future (Milestone 3):
    - Extract preferences from natural language
    - Update preferences based on user feedback
    """

    def __init__(self, storage: Optional[MemoryStorage] = None):
        """
        Initialize the profile agent.

        Args:
            storage: MemoryStorage instance. If None, creates a new one
        """
        self.storage = storage or MemoryStorage()
        log_info("profile_agent_initialized")

    def load_profile(self, user_id: str) -> UserProfile:
        """
        Load user profile.

        Creates a new profile if user doesn't exist.

        Args:
            user_id: User identifier

        Returns:
            UserProfile: User profile
        """
        profile = self.storage.load_profile(user_id)
        log_info(
            "profile_loaded_by_agent",
            user_id=user_id,
            favorite_genres_count=len(profile.favorite_genres),
            disliked_genres_count=len(profile.disliked_genres),
        )
        return profile

    def save_profile(self, profile: UserProfile) -> None:
        """
        Save user profile.

        Args:
            profile: UserProfile to save
        """
        self.storage.save_profile(profile)
        log_info("profile_saved_by_agent", user_id=profile.user_id)

    def get_favorite_genres(self, user_id: str) -> list[str]:
        """
        Get user's favorite genres.

        Args:
            user_id: User identifier

        Returns:
            list[str]: List of favorite genres
        """
        profile = self.load_profile(user_id)
        return profile.favorite_genres

    def get_disliked_genres(self, user_id: str) -> list[str]:
        """
        Get user's disliked genres.

        Args:
            user_id: User identifier

        Returns:
            list[str]: List of disliked genres
        """
        profile = self.load_profile(user_id)
        return profile.disliked_genres

    def get_favorite_artists(self, user_id: str) -> list[str]:
        """
        Get user's favorite artists.

        Args:
            user_id: User identifier

        Returns:
            list[str]: List of favorite artists
        """
        profile = self.load_profile(user_id)
        return profile.favorite_artists

    def update_preferences(
        self,
        user_id: str,
        favorite_genres: Optional[list[str]] = None,
        disliked_genres: Optional[list[str]] = None,
        favorite_artists: Optional[list[str]] = None,
        location: Optional[str] = None,
    ) -> UserProfile:
        """
        Update user preferences.

        This is a simple version for Milestone 2.
        In Milestone 3, we'll add NLP-based preference extraction.

        Args:
            user_id: User identifier
            favorite_genres: Genres to add to favorites
            disliked_genres: Genres to add to dislikes
            favorite_artists: Artists to add to favorites
            location: User location

        Returns:
            UserProfile: Updated profile
        """
        profile = self.load_profile(user_id)

        if favorite_genres:
            for genre in favorite_genres:
                profile.add_favorite_genre(genre)

        if disliked_genres:
            for genre in disliked_genres:
                profile.add_disliked_genre(genre)

        if favorite_artists:
            for artist in favorite_artists:
                profile.add_favorite_artist(artist)

        if location:
            profile.location = location

        self.save_profile(profile)

        log_info(
            "preferences_updated",
            user_id=user_id,
            favorite_genres=len(profile.favorite_genres),
            disliked_genres=len(profile.disliked_genres),
            favorite_artists=len(profile.favorite_artists),
        )

        return profile
