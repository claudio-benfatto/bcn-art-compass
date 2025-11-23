"""
Profile Agent - manages user preferences and long-term memory.

This agent handles loading and updating user profiles.
In Milestone 3, extracts preferences from natural language using LLM.
Supports both Google Gemini (cloud) and Ollama (local) models.
"""

import os
from typing import Optional

from google import genai

from memory.models import UserProfile
from memory.storage import MemoryStorage
from observability import log_info

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class ProfileAgent:
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
        storage: Optional[MemoryStorage] = None,
        model_name: str = "gemini-2.5-flash",
        use_local_llm: Optional[bool] = None,  # Auto-detect based on GOOGLE_API_KEY
        local_model: str = "llama3.2",
    ):
        """
        Initialize the profile agent.

        Args:
            storage: MemoryStorage instance. If None, creates a new one
            model_name: Gemini model to use for preference extraction
            use_local_llm: Force use of local LLM. If None, auto-detect based on GOOGLE_API_KEY
            local_model: Ollama model to use (default: llama3.2)
        """
        self.storage = storage or MemoryStorage()
        
        # Determine which LLM to use
        if use_local_llm is None:
            # Auto-detect: use local if no API key or explicit flag
            env_flag = os.getenv("USE_LOCAL_LLM", "").lower()
            if env_flag in ("true", "1", "yes"):
                use_local_llm = True
            elif env_flag in ("false", "0", "no"):
                use_local_llm = False
            else:
                use_local_llm = "GOOGLE_API_KEY" not in os.environ
        
        self.use_local_llm = use_local_llm
        self.local_model = local_model
        
        if self.use_local_llm:
            if not OLLAMA_AVAILABLE:
                log_info(
                    "ollama_not_available",
                    level="warning",
                    message="Ollama not installed, falling back to simple rule-based extraction"
                )
                self.model = None
                self.llm_type = "rule-based"
            else:
                self.model = None  # Ollama doesn't need model initialization
                self.llm_type = "ollama"
                log_info("profile_agent_initialized", model=local_model, llm_type="local (ollama)")
        else:
            # Configure Gemini API key
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                log_info(
                    "google_api_key_missing",
                    level="warning",
                    message="GOOGLE_API_KEY not set, falling back to rule-based extraction"
                )
                self.model = None
                self.llm_type = "rule-based"
            else:
                # Use the new google-genai SDK (stable v1 API)
                self.client = genai.Client(api_key=api_key)
                self.model = model_name
                self.llm_type = "gemini"
                log_info("profile_agent_initialized", model=model_name, llm_type="cloud (gemini)")

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
        log_info("extracting_preferences", user_id=user_id, text=text, llm_type=self.llm_type)

        if self.llm_type == "rule-based":
            # Simple rule-based extraction as fallback
            extracted = self._extract_with_rules(text)
        elif self.llm_type == "ollama":
            # Use local Ollama model
            extracted = await self._extract_with_ollama(text)
        else:
            # Use Google Gemini
            extracted = await self._extract_with_gemini(text)

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

    def _extract_with_rules(self, text: str) -> dict:
        """
        Simple rule-based preference extraction.
        
        Fallback when no LLM is available.
        """
        import re
        
        text_lower = text.lower()
        result = {
            "favorite_genres": [],
            "disliked_genres": [],
            "favorite_artists": [],
            "location": None
        }
        
        # Common art genres
        genres = [
            "contemporary art", "modern art", "abstract art", "sculpture",
            "painting", "photography", "video art", "performance art",
            "installation", "digital art", "street art", "conceptual art"
        ]
        
        # Detect likes
        like_patterns = [
            r"i (love|like|enjoy|prefer|am into)",
            r"i'?m (interested in|a fan of)",
            r"my favorite.* (is|are)"
        ]
        
        # Detect dislikes
        dislike_patterns = [
            r"i (don'?t|do not) (like|enjoy)",
            r"i (hate|dislike)",
            r"not (a fan|interested in)",
        ]
        
        # Extract genres
        for genre in genres:
            if genre in text_lower:
                # Check if it's a like or dislike
                for pattern in like_patterns:
                    if re.search(pattern + r".*" + re.escape(genre), text_lower):
                        result["favorite_genres"].append(genre)
                        break
                else:
                    for pattern in dislike_patterns:
                        if re.search(pattern + r".*" + re.escape(genre), text_lower):
                            result["disliked_genres"].append(genre)
                            break
        
        return result

    async def _extract_with_ollama(self, text: str) -> dict:
        """Extract preferences using local Ollama model."""
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
Output: {{"favorite_genres": ["contemporary sculpture"], "disliked_genres": [], "favorite_artists": ["Picasso"], "location": null}}

Now analyze the user statement and return only the JSON object:"""

        try:
            response = ollama.chat(
                model=self.local_model,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response["message"]["content"].strip()
            
            # Clean up response
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
            return extracted
            
        except Exception as e:
            log_info(
                "ollama_extraction_error",
                error=str(e),
                fallback="rule-based"
            )
            # Fallback to rule-based
            return self._extract_with_rules(text)

    async def _extract_with_gemini(self, text: str) -> dict:
        """Extract preferences using Google Gemini with the new google-genai SDK."""
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
            # Call Gemini using the new SDK
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
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
            return extracted

        except Exception as e:
            log_info(
                "gemini_extraction_error",
                error=str(e),
                fallback="rule-based"
            )
            # Fallback to rule-based
            return self._extract_with_rules(text)
