"""Profile management tools for ADK agents.

These tools provide user profile operations that can be used by ADK agents:
- Loading user profiles
- Updating preferences
- Extracting preferences from natural language

All tools use closure pattern for dependency injection (no global state).
"""

import time
from typing import Any, Callable, Optional

from agents.preference_extractor import PreferenceExtractor, create_preference_extractor
from memory.storage import MemoryStorage
from memory.storage_interface import ProfileStorage
from observability import log_error, log_info


def create_profile_tools(
    storage: Optional[ProfileStorage] = None,
    preference_extractor: Optional[PreferenceExtractor] = None,
) -> tuple[Callable, Callable, Callable]:
    """Factory function that creates profile tools with dependencies captured in closure.

    This pattern avoids global state by creating tool functions with dependencies
    baked into their closures. The returned functions have the exact signatures
    expected by ADK agents.

    Args:
        storage: ProfileStorage instance (defaults to MemoryStorage if None)
        preference_extractor: PreferenceExtractor instance (auto-created if None)

    Returns:
        Tuple of (get_profile_tool, update_profile_tool, extract_preferences_tool)

    Example:
        >>> storage = MemoryStorage()
        >>> get_profile, update_profile, extract_prefs = create_profile_tools(storage)
        >>> agent = Agent(tools=[get_profile, update_profile, extract_prefs], ...)
    """
    # Initialize dependencies with defaults if not provided
    _storage = storage or MemoryStorage()
    _preference_extractor = preference_extractor or create_preference_extractor()

    log_info(
        "profile_tools_created",
        has_storage=True,
        has_extractor=True,
    )

    def get_profile_tool(user_id: str) -> dict[str, Any]:
        """Load a user's profile including preferences and location.

        This tool retrieves the complete user profile from storage.
        If the user doesn't exist, a new profile is created.

        Args:
            user_id: Unique identifier for the user

        Returns:
            Dictionary containing the user profile with fields:
            - user_id: User identifier
            - location: User's location (optional)
            - favorite_genres: List of genres the user likes
            - disliked_genres: List of genres the user dislikes
            - favorite_artists: List of the user's favorite artists

        Example:
            >>> profile = get_profile_tool("user123")
            >>> print(profile["favorite_genres"])
            ["contemporary art", "sculpture"]
        """
        profile = _storage.load_profile(user_id)

        log_info(
            "profile_loaded_by_tool",
            user_id=user_id,
            favorite_genres_count=len(profile.favorite_genres),
            disliked_genres_count=len(profile.disliked_genres),
        )

        result = profile.model_dump()
        log_info("tool_return_type", tool="get_profile_tool", type=str(type(result)), value=repr(result))
        if not isinstance(result, dict):
            return {"result": result}
        return result

    def update_profile_tool(
        user_id: str,
        favorite_genres: Optional[list[str]] = None,
        disliked_genres: Optional[list[str]] = None,
        favorite_artists: Optional[list[str]] = None,
        location: Optional[str] = None,
        remove_favorite_genres: Optional[list[str]] = None,
        remove_disliked_genres: Optional[list[str]] = None,
        remove_favorite_artists: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Update a user's preferences and profile information.

        This tool allows explicit updates to user preferences. Any parameter
        that is None will not be modified in the profile.

        Supports removal lists. Return structure includes diff describing
        additions and removals for agent confirmation.

        Args:
            user_id: Unique identifier for the user
            favorite_genres: Genres to add to the user's favorites (optional)
            disliked_genres: Genres to add to the user's dislikes (optional)
            favorite_artists: Artists to add to favorites (optional)
            location: Update the user's location (optional)
            remove_favorite_genres: Genres to remove from favorites (optional)
            remove_disliked_genres: Genres to remove from dislikes (optional)
            remove_favorite_artists: Artists to remove from favorites (optional)

        Returns:
            Dictionary containing:
            {
              "profile": <full profile dict>,
              "updated": {
                 "favorite_genres_added": [...],
                 "favorite_genres_removed": [...],
                 "favorite_genres_not_found": [...],
                 "disliked_genres_added": [...],
                 "disliked_genres_removed": [...],
                 "disliked_genres_not_found": [...],
                 "favorite_artists_added": [...],
                 "favorite_artists_removed": [...],
                 "favorite_artists_not_found": [...],
                 "location_changed": bool
              }
            }

        Example:
            >>> profile = update_profile_tool(
            ...     "user123",
            ...     favorite_genres=["contemporary art"],
            ...     location="Barcelona"
            ... )
        """
        profile = _storage.load_profile(user_id)

        # Normalization helper (shared with extract) kept simple here
        def _normalize(items: Optional[list[str]]) -> list[str]:
            if not items:
                return []
            cleaned = {s.strip().lower() for s in items if isinstance(s, str) and s.strip()}
            return [c for c in sorted(cleaned)]

        fav_genres_in = _normalize(favorite_genres)
        dis_genres_in = _normalize(disliked_genres)
        fav_artists_in = _normalize(favorite_artists)
        # Keep original inputs for casing while using normalized sets for matching
        rem_fav_genres_orig = remove_favorite_genres or []
        rem_dis_genres_orig = remove_disliked_genres or []
        rem_fav_artists_orig = remove_favorite_artists or []

        # Normalized removal lists (unused now but kept for potential future validation) removed to avoid lint errors.

        favorite_genres_added: list[str] = []
        favorite_genres_removed: list[str] = []
        favorite_genres_not_found: list[str] = []
        disliked_genres_added: list[str] = []
        disliked_genres_removed: list[str] = []
        disliked_genres_not_found: list[str] = []
        favorite_artists_added: list[str] = []
        favorite_artists_removed: list[str] = []
        favorite_artists_not_found: list[str] = []
        location_changed = False

        # Additions
        for genre in fav_genres_in:
            before = set(profile.favorite_genres)
            profile.add_favorite_genre(genre)
            if genre in profile.favorite_genres and genre not in before:
                favorite_genres_added.append(genre)

        for genre in dis_genres_in:
            before = set(profile.disliked_genres)
            profile.add_disliked_genre(genre)
            if genre in profile.disliked_genres and genre not in before:
                disliked_genres_added.append(genre)

        for artist in fav_artists_in:
            before = set(profile.favorite_artists)
            profile.add_favorite_artist(artist)
            if artist in profile.favorite_artists and artist not in before:
                favorite_artists_added.append(artist)
        # Removals
        for raw in rem_fav_genres_orig:
            norm = raw.strip().lower() if isinstance(raw, str) else raw
            if norm in profile.favorite_genres:
                profile.remove_favorite_genre(norm)
                favorite_genres_removed.append(raw)
            else:
                favorite_genres_not_found.append(raw)

        for raw in rem_dis_genres_orig:
            norm = raw.strip().lower() if isinstance(raw, str) else raw
            if norm in profile.disliked_genres:
                profile.remove_disliked_genre(norm)
                disliked_genres_removed.append(raw)
            else:
                disliked_genres_not_found.append(raw)

        for raw in rem_fav_artists_orig:
            norm = raw.strip().lower() if isinstance(raw, str) else raw
            if norm in profile.favorite_artists:
                profile.remove_favorite_artist(norm)
                favorite_artists_removed.append(raw)
            else:
                favorite_artists_not_found.append(raw)

        if location is not None:
            original_location = profile.location
            if location != original_location:
                profile.location = location
                location_changed = True
        
        _storage.save_profile(profile)

        log_info(
            "profile_updated_by_tool",
            user_id=user_id,
            favorite_genres=len(profile.favorite_genres),
            disliked_genres=len(profile.disliked_genres),
            favorite_artists=len(profile.favorite_artists),
            favorite_genres_added=len(favorite_genres_added),
            favorite_genres_removed=len(favorite_genres_removed),
            disliked_genres_added=len(disliked_genres_added),
            disliked_genres_removed=len(disliked_genres_removed),
            favorite_artists_added=len(favorite_artists_added),
            favorite_artists_removed=len(favorite_artists_removed),
        )
        result = {
            "profile": profile.model_dump(),
            "updated": {
                "favorite_genres_added": favorite_genres_added,
                "favorite_genres_removed": favorite_genres_removed,
                "favorite_genres_not_found": favorite_genres_not_found,
                "disliked_genres_added": disliked_genres_added,
                "disliked_genres_removed": disliked_genres_removed,
                "disliked_genres_not_found": disliked_genres_not_found,
                "favorite_artists_added": favorite_artists_added,
                "favorite_artists_removed": favorite_artists_removed,
                "favorite_artists_not_found": favorite_artists_not_found,
                "location_changed": location_changed,
            },
        }
        log_info("tool_return_type", tool="update_profile_tool", type=str(type(result)), value=repr(result))
        if not isinstance(result, dict):
            return {"result": result}
        return result

    async def extract_preferences_tool(user_id: str, text: str) -> dict[str, Any]:
        """Async: Extract and apply user preferences from natural language.

        Enhancements over previous implementation:
        - Fully async (awaits extractor instead of blocking run_until_complete)
        - Normalizes terms (lowercase, strip) and deduplicates
        - Returns structured diff alongside full profile
        - Logs duration and counts of additions
        - Error path returns structured error with unchanged profile

        Return schema:
        {
          "profile": <full profile dict>,
          "updated": {
             "favorite_genres_added": [...],
             "disliked_genres_added": [...],
             "favorite_artists_added": [...],
             "location_changed": bool
          }
        }
        On error:
        {
          "error": "<message>",
          "profile": <full profile dict>,
          "updated": {}
        }
        """
        start = time.time()
        log_info("extracting_preferences_via_tool", user_id=user_id, text=text[:120])

        def _normalize(items: Optional[list[str]]) -> list[str]:
            if not items:
                return []
            cleaned = {s.strip().lower() for s in items if isinstance(s, str) and s.strip()}
            return sorted(cleaned)

        try:
            extracted = await _preference_extractor.extract(text)
            log_info(
                "preferences_extracted_by_tool",
                user_id=user_id,
                extracted=extracted,
            )

            profile = _storage.load_profile(user_id)

            fav_genres_in = _normalize(extracted.get("favorite_genres"))
            dis_genres_in = _normalize(extracted.get("disliked_genres"))
            fav_artists_in = _normalize(extracted.get("favorite_artists"))
            location_in = extracted.get("location")

            favorite_genres_added: list[str] = []
            disliked_genres_added: list[str] = []
            favorite_artists_added: list[str] = []
            location_changed = False

            # Patch: always use normalized, deduped values for additions
            for genre in fav_genres_in:
                norm_genre = genre.strip().lower()
                before = set(g.strip().lower() for g in profile.favorite_genres)
                profile.add_favorite_genre(norm_genre)
                after = set(g.strip().lower() for g in profile.favorite_genres)
                if norm_genre in after and norm_genre not in before:
                    favorite_genres_added.append(norm_genre)

            for genre in dis_genres_in:
                norm_genre = genre.strip().lower()
                before = set(g.strip().lower() for g in profile.disliked_genres)
                profile.add_disliked_genre(norm_genre)
                after = set(g.strip().lower() for g in profile.disliked_genres)
                if norm_genre in after and norm_genre not in before:
                    disliked_genres_added.append(norm_genre)

            for artist in fav_artists_in:
                norm_artist = artist.strip().lower()
                before = set(a.strip().lower() for a in profile.favorite_artists)
                profile.add_favorite_artist(norm_artist)
                after = set(a.strip().lower() for a in profile.favorite_artists)
                if norm_artist in after and norm_artist not in before:
                    favorite_artists_added.append(norm_artist)

            if location_in and location_in != profile.location:
                profile.location = location_in
                location_changed = True

            _storage.save_profile(profile)

            duration_ms = int((time.time() - start) * 1000)
            log_info(
                "profile_updated_after_extraction",
                user_id=user_id,
                duration_ms=duration_ms,
                favorite_genres_added=len(favorite_genres_added),
                disliked_genres_added=len(disliked_genres_added),
                favorite_artists_added=len(favorite_artists_added),
                location_changed=location_changed,
            )

            return {
                "profile": profile.model_dump(),
                "updated": {
                    "favorite_genres_added": favorite_genres_added,
                    "disliked_genres_added": disliked_genres_added,
                    "favorite_artists_added": favorite_artists_added,
                    "location_changed": location_changed,
                },
            }
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            log_error(
                "preference_extraction_failed_in_tool",
                user_id=user_id,
                error=str(e),
                duration_ms=duration_ms,
                error_type=type(e).__name__,
            )
            profile = _storage.load_profile(user_id)
            result = {"error": str(e), "profile": profile.model_dump(), "updated": {}}
            log_info("tool_return_type", tool="update_profile_tool_error", type=str(type(result)), value=repr(result))
            if not isinstance(result, dict):
                return {"result": result}
            return result

    return get_profile_tool, update_profile_tool, extract_preferences_tool
