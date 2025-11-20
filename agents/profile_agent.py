"""
Profile Agent - manages user preferences and long-term memory.

This agent handles loading and updating user profiles.
In Milestone 3, extracts preferences from natural language using LLM.
"""

from typing import Optional

import google.generativeai as genai

from memory.models import UserProfile
from memory.storage import MemoryStorage
from observability import log_info


class ProfileAgent:
    """
    Profile agent with NLP-based preference extraction.

    Responsibilities:
    - Load user profile from storage
    - Extract preferences from natural language
    - Update preferences based on user feedback
    - Save profile updates
    """

    def __init__(self, storage: Optional[MemoryStorage] = None, model_name: str = "gemini-1.5-flash"):
        """
        Initialize the profile agent.

        Args:
            storage: MemoryStorage instance. If None, creates a new one
            model_name: Gemini model to use for preference extraction
        """
        self.storage = storage or MemoryStorage()
        self.model = genai.GenerativeModel(model_name)
        log_info("profile_agent_initialized", model=model_name)

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

        # Construct prompt for Gemini
        prompt = f"""You are a preference extraction assistant for a cultural events recommender system.

Analyze the following user statement and extract any preferences about:
- favorite_genres: Art/event genres they LIKE (contemporary art, sculpture, painting, etc.)
- disliked_genres: Art/event genres they DON'T like
- favorite_artists: Specific artists they mention favorably
- location: Location they mention (city, neighborhood)

User statement: "{text}"

Return ONLY a valid JSON object with these fields (use empty lists if nothing found):
{{
  "favorite_genres": [],
  "disliked_genres": [],
  "favorite_artists": [],
  "location": null
}}

Examples:
Input: "I don't like video art"
Output: {{"favorite_genres": [], "disliked_genres": ["video art"], "favorite_artists": [], "location": null}}

Input: "I love contemporary sculpture and Picasso"
Output: {{"favorite_genres": ["contemporary sculpture"], "disliked_genres": [],
         "favorite_artists": ["Picasso"], "location": null}}

Now analyze the user statement and return only the JSON object:"""

        try:
            # Call Gemini
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # Clean up response (remove markdown code blocks if present)
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            # Parse JSON
            import json
            extracted = json.loads(result_text)

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
            log_info(
                "preference_extraction_error",
                user_id=user_id,
                error=str(e),
                text=text,
            )
            # Return existing profile on error
            return self.load_profile(user_id)
