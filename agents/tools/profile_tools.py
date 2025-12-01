"""Profile management tools for ADK agents.

These tools provide user profile operations that can be used by ADK agents:
- Loading user profiles
- Updating preferences
- Extracting preferences from natural language
"""

import time
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from agents.preference_extractor import PreferenceExtractor, create_preference_extractor
from memory.storage import MemoryStorage
from memory.storage_interface import ProfileStorage
from memory.models import UserProfile
from observability import log_error, log_info


class ProfileUpdateDiff(BaseModel):
    """Structured diff describing which profile fields were updated."""

    favorite_genres_added: list[str] = Field(default_factory=list)
    favorite_genres_removed: list[str] = Field(default_factory=list)
    favorite_genres_not_found: list[str] = Field(default_factory=list)

    disliked_genres_added: list[str] = Field(default_factory=list)
    disliked_genres_removed: list[str] = Field(default_factory=list)
    disliked_genres_not_found: list[str] = Field(default_factory=list)

    favorite_artists_added: list[str] = Field(default_factory=list)
    favorite_artists_removed: list[str] = Field(default_factory=list)
    favorite_artists_not_found: list[str] = Field(default_factory=list)

    location_changed: bool = False


class ProfileUpdateResult(BaseModel):
    """Return schema for explicit profile updates via tools."""

    profile: dict[str, Any]
    updated: ProfileUpdateDiff


class ExtractPreferencesResult(BaseModel):
    """Return schema for extract_preferences_tool success path."""

    profile: dict[str, Any]
    updated: ProfileUpdateDiff


def create_profile_tools(
    storage: Optional[ProfileStorage] = None,
    preference_extractor: Optional[PreferenceExtractor] = None,
) -> tuple[Callable, Callable, Callable]:
    """Factory function that creates profile tools with dependencies captured in closure.

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

    # ---------- Pure helpers: normalization & "apply" semantics ----------

    def _normalize_prefs(items: Optional[list[str]]) -> list[str]:
        """Normalize preference lists: strip, lowercase, dedupe, sorted."""
        if not items:
            return []
        cleaned = {s.strip().lower() for s in items if isinstance(s, str) and s.strip()}
        return sorted(cleaned)

    def _apply_additions_to_profile(
        profile: UserProfile,
        fav_genres: list[str],
        dis_genres: list[str],
        fav_artists: list[str],
    ) -> tuple[list[str], list[str], list[str]]:
        """Apply additions to profile, returning (fav_added, dis_added, artists_added)."""
        favorite_genres_added: list[str] = []
        disliked_genres_added: list[str] = []
        favorite_artists_added: list[str] = []

        for genre in fav_genres:
            norm = genre.strip().lower()
            before = {g.strip().lower() for g in profile.favorite_genres}
            profile.add_favorite_genre(norm)
            after = {g.strip().lower() for g in profile.favorite_genres}
            if norm in after and norm not in before:
                favorite_genres_added.append(norm)

        for genre in dis_genres:
            norm = genre.strip().lower()
            before = {g.strip().lower() for g in profile.disliked_genres}
            profile.add_disliked_genre(norm)
            after = {g.strip().lower() for g in profile.disliked_genres}
            if norm in after and norm not in before:
                disliked_genres_added.append(norm)

        for artist in fav_artists:
            norm = artist.strip().lower()
            before = {a.strip().lower() for a in profile.favorite_artists}
            profile.add_favorite_artist(norm)
            after = {a.strip().lower() for a in profile.favorite_artists}
            if norm in after and norm not in before:
                favorite_artists_added.append(norm)

        return favorite_genres_added, disliked_genres_added, favorite_artists_added

    def _apply_extracted_preferences(
        profile: UserProfile,
        extracted: dict[str, Any],
    ) -> ProfileUpdateDiff:
        """Apply extracted preferences onto a profile and return the structured diff.

        This is the single place that knows how to go from the extractor's
        output schema to concrete profile mutations + diff, separating the
        "extract" concern (LLM) from "apply" (business rules).
        """
        fav_genres_in = _normalize_prefs(extracted.get("favorite_genres"))
        dis_genres_in = _normalize_prefs(extracted.get("disliked_genres"))
        fav_artists_in = _normalize_prefs(extracted.get("favorite_artists"))
        location_in = extracted.get("location")

        favorite_genres_added, disliked_genres_added, favorite_artists_added = _apply_additions_to_profile(
            profile,
            fav_genres_in,
            dis_genres_in,
            fav_artists_in,
        )

        location_changed = False
        if location_in and location_in != profile.location:
            profile.location = location_in
            location_changed = True

        # For extracted prefs we only ever add; removals/not_found remain defaults.
        return ProfileUpdateDiff(
            favorite_genres_added=favorite_genres_added,
            disliked_genres_added=disliked_genres_added,
            favorite_artists_added=favorite_artists_added,
            location_changed=location_changed,
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

        fav_genres_in = _normalize_prefs(favorite_genres)
        dis_genres_in = _normalize_prefs(disliked_genres)
        fav_artists_in = _normalize_prefs(favorite_artists)
        # Keep original inputs for casing while using normalized sets for matching
        rem_fav_genres_orig = remove_favorite_genres or []
        rem_dis_genres_orig = remove_disliked_genres or []
        rem_fav_artists_orig = remove_favorite_artists or []

        # Normalized removal lists (unused now but kept for potential future validation) removed to avoid lint errors.

        favorite_genres_removed: list[str] = []
        favorite_genres_not_found: list[str] = []
        disliked_genres_removed: list[str] = []
        disliked_genres_not_found: list[str] = []
        favorite_artists_removed: list[str] = []
        favorite_artists_not_found: list[str] = []
        location_changed = False

        # Additions (shared logic with extract_preferences_tool)
        (
            favorite_genres_added,
            disliked_genres_added,
            favorite_artists_added,
        ) = _apply_additions_to_profile(
            profile,
            fav_genres_in,
            dis_genres_in,
            fav_artists_in,
        )
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
        # Build structured diff and result using Pydantic models, but return as dict
        diff = ProfileUpdateDiff(
            favorite_genres_added=favorite_genres_added,
            favorite_genres_removed=favorite_genres_removed,
            favorite_genres_not_found=favorite_genres_not_found,
            disliked_genres_added=disliked_genres_added,
            disliked_genres_removed=disliked_genres_removed,
            disliked_genres_not_found=disliked_genres_not_found,
            favorite_artists_added=favorite_artists_added,
            favorite_artists_removed=favorite_artists_removed,
            favorite_artists_not_found=favorite_artists_not_found,
            location_changed=location_changed,
        )
        result_model = ProfileUpdateResult(
            profile=profile.model_dump(),
            updated=diff,
        )
        result = result_model.model_dump()
        log_info("tool_return_type", tool="update_profile_tool", type=str(type(result)), value=repr(result))
        if not isinstance(result, dict):
            return {"result": result}
        return result

    async def extract_preferences_tool(user_id: str, text: str) -> dict[str, Any]:
        """Async: Extract and apply user preferences from natural language.

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

        try:
            # --- Extract: LLM-side responsibility ---
            extracted = await _preference_extractor.extract(text)
            log_info(
                "preferences_extracted_by_tool",
                user_id=user_id,
                extracted=extracted,
            )

            # --- Apply: business rules over the stored profile ---
            profile = _storage.load_profile(user_id)
            diff = _apply_extracted_preferences(profile, extracted)

            _storage.save_profile(profile)

            duration_ms = int((time.time() - start) * 1000)
            log_info(
                "profile_updated_after_extraction",
                user_id=user_id,
                duration_ms=duration_ms,
                favorite_genres_added=len(diff.favorite_genres_added),
                disliked_genres_added=len(diff.disliked_genres_added),
                favorite_artists_added=len(diff.favorite_artists_added),
                location_changed=diff.location_changed,
            )

            result_model = ExtractPreferencesResult(
                profile=profile.model_dump(),
                updated=diff,
            )
            return result_model.model_dump()
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
