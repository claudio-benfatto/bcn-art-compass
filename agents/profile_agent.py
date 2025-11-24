"""
Profile Agent - manages user preferences and long-term memory.

This agent handles loading and updating user profiles.
In Milestone 3, extracts preferences from natural language using LLM.
Supports both Google Gemini (cloud) and Ollama (local) models.

A2A-compliant for future agent-to-agent communication.
"""

from typing import Optional

from agents.a2a_protocol import A2AAgent, A2AMessage, AgentCapability, MessageType
from agents.preference_extractor import PreferenceExtractor, create_preference_extractor
from memory.models import UserProfile
from memory.storage import MemoryStorage
from memory.storage_interface import ProfileStorage
from observability import log_error, log_info


class ProfileAgent(A2AAgent):
    """
    Profile agent with NLP-based preference extraction.

    Responsibilities:
    - Load user profile from storage
    - Extract preferences from natural language
    - Update preferences based on user feedback
    - Save profile updates
    """

    def __init__(
        self,
        storage: Optional[ProfileStorage] = None,
        preference_extractor: Optional[PreferenceExtractor] = None,
    ):
        """
        Initialize the profile agent.

        Args:
            storage: ProfileStorage instance (e.g., MemoryStorage, FirestoreStorage). If None, creates a MemoryStorage
            preference_extractor: PreferenceExtractor instance. If None, creates one automatically
        """
        # Initialize A2A protocol base
        super().__init__(agent_id="profile_agent", name="ProfileAgent")

        # Register capabilities
        self.register_capability(AgentCapability(
            name="load_profile",
            description="Load user profile from storage",
            input_schema={"user_id": "string"},
            output_schema={"profile": "UserProfile"},
        ))
        self.register_capability(AgentCapability(
            name="extract_preferences",
            description="Extract user preferences from natural language",
            input_schema={"user_id": "string", "text": "string"},
            output_schema={"profile": "UserProfile"},
        ))

        self.storage = storage or MemoryStorage()
        self.preference_extractor = preference_extractor or create_preference_extractor()

        log_info("profile_agent_initialized", with_extractor=preference_extractor is not None)

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

    async def extract_preferences(self, user_id: str, text: str) -> UserProfile:
        """
        Extract preferences from natural language text using LLM.

        Supports multiple backends:
        - Google Gemini (cloud, requires API key)
        - Ollama (local, free)
        - Rule-based fallback (simple keyword matching)

        Parses user statements like:
        - "I don't like video art"
        - "I love contemporary sculpture"
        - "My favorite artist is Picasso"

        Args:
            user_id: Unique identifier for the user
            text: Natural language text expressing preferences

        Returns:
            Updated UserProfile after extraction

        Example:
            >>> profile = await agent.extract_preferences("user123", "I don't like performance art")
            >>> "performance art" in profile.disliked_genres
            True
        """
        log_info("extracting_preferences", user_id=user_id, text=text)

        try:
            # Use the injected preference extractor
            extracted = await self.preference_extractor.extract(text)

            log_info(
                "preferences_extracted",
                user_id=user_id,
                extracted=extracted,
            )

            # Update profile using existing update_preferences method
            profile = self.update_preferences(
                user_id=user_id,
                favorite_genres=extracted.get("favorite_genres", []),
                disliked_genres=extracted.get("disliked_genres", []),
                favorite_artists=extracted.get("favorite_artists", []),
                location=extracted.get("location"),
            )

            return profile

        except Exception as e:
            log_error("preference_extraction_failed", user_id=user_id, error=str(e))
            # Return existing profile without changes
            return self.load_profile(user_id)

    def process(self, message: A2AMessage) -> A2AMessage:
        """
        Process A2A protocol message.

        Args:
            message: Input A2A message

        Returns:
            Response A2A message
        """
        if message.message_type != MessageType.REQUEST:
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content={"error": "Only REQUEST messages supported"},
                correlation_id=message.correlation_id,
            )

        action = message.content.get("action")

        if action == "load_profile":
            user_id = message.content.get("user_id")
            profile = self.load_profile(user_id)
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.RESPONSE,
                content={"profile": profile.model_dump() if profile else None},
                correlation_id=message.correlation_id,
            )

        elif action == "extract_preferences":
            user_id = message.content.get("user_id")
            text = message.content.get("text")
            profile = self.extract_and_update(user_id, text)
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.RESPONSE,
                content={"profile": profile.model_dump() if profile else None},
                correlation_id=message.correlation_id,
            )

        else:
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content={"error": f"Unknown action: {action}"},
                correlation_id=message.correlation_id,
            )
