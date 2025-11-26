"""Profile management tools for ADK agents.

These tools provide user profile operations that can be used by ADK agents:
- Loading user profiles
- Updating preferences
- Extracting preferences from natural language

All tools are stateless and use dependency injection for storage.
"""

import asyncio
from typing import Any, Optional

from agents.preference_extractor import PreferenceExtractor, create_preference_extractor
from memory.storage import MemoryStorage
from memory.storage_interface import ProfileStorage
from observability import log_error, log_info


# Global storage instance (can be replaced with dependency injection)
_storage: Optional[ProfileStorage] = None
_preference_extractor: Optional[PreferenceExtractor] = None


def initialize_profile_tools(
    storage: Optional[ProfileStorage] = None,
    preference_extractor: Optional[PreferenceExtractor] = None,
) -> None:
    """Initialize the profile tools with storage and extractor dependencies.
    
    This must be called before using the tools, typically during application startup.
    
    Args:
        storage: ProfileStorage instance (defaults to MemoryStorage)
        preference_extractor: PreferenceExtractor instance (auto-created if None)
    """
    global _storage, _preference_extractor
    _storage = storage or MemoryStorage()
    _preference_extractor = preference_extractor or create_preference_extractor()
    log_info("profile_tools_initialized", has_storage=True, has_extractor=True)


def _get_storage() -> ProfileStorage:
    """Get the storage instance, initializing if needed."""
    global _storage
    if _storage is None:
        _storage = MemoryStorage()
        log_info("profile_storage_auto_initialized")
    return _storage


def _get_preference_extractor() -> PreferenceExtractor:
    """Get the preference extractor, initializing if needed."""
    global _preference_extractor
    if _preference_extractor is None:
        _preference_extractor = create_preference_extractor()
        log_info("preference_extractor_auto_initialized")
    return _preference_extractor


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
    storage = _get_storage()
    profile = storage.load_profile(user_id)
    
    log_info(
        "profile_loaded_by_tool",
        user_id=user_id,
        favorite_genres_count=len(profile.favorite_genres),
        disliked_genres_count=len(profile.disliked_genres),
    )
    
    return profile.model_dump()


def update_profile_tool(
    user_id: str,
    favorite_genres: Optional[list[str]] = None,
    disliked_genres: Optional[list[str]] = None,
    favorite_artists: Optional[list[str]] = None,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Update a user's preferences and profile information.
    
    This tool allows explicit updates to user preferences. Any parameter
    that is None will not be modified in the profile.
    
    Args:
        user_id: Unique identifier for the user
        favorite_genres: Genres to add to the user's favorites (optional)
        disliked_genres: Genres to add to the user's dislikes (optional)
        favorite_artists: Artists to add to favorites (optional)
        location: Update the user's location (optional)
        
    Returns:
        Dictionary containing the updated user profile
        
    Example:
        >>> profile = update_profile_tool(
        ...     "user123",
        ...     favorite_genres=["contemporary art"],
        ...     location="Barcelona"
        ... )
    """
    storage = _get_storage()
    profile = storage.load_profile(user_id)
    
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
    
    storage.save_profile(profile)
    
    log_info(
        "profile_updated_by_tool",
        user_id=user_id,
        favorite_genres=len(profile.favorite_genres),
        disliked_genres=len(profile.disliked_genres),
        favorite_artists=len(profile.favorite_artists),
    )
    
    return profile.model_dump()


def extract_preferences_tool(user_id: str, text: str) -> dict[str, Any]:
    """Extract and apply user preferences from natural language.
    
    This tool uses an LLM to parse user statements about their preferences
    and automatically updates their profile. It can understand statements like:
    - "I don't like video art"
    - "I love contemporary sculpture"
    - "My favorite artist is Picasso"
    - "I'm in Barcelona"
    
    The tool uses Google Gemini or Ollama (with fallback to rule-based extraction)
    to understand the user's intent and extract structured preferences.
    
    Args:
        user_id: Unique identifier for the user
        text: Natural language text expressing preferences
        
    Returns:
        Dictionary containing the updated user profile after extraction
        
    Example:
        >>> profile = extract_preferences_tool(
        ...     "user123",
        ...     "I really enjoy contemporary art and photography, but I don't like performance art"
        ... )
        >>> "contemporary art" in profile["favorite_genres"]
        True
        >>> "performance art" in profile["disliked_genres"]
        True
    """
    log_info("extracting_preferences_via_tool", user_id=user_id, text=text[:100])
    
    try:
        extractor = _get_preference_extractor()
        
        # Run the async extraction in the current event loop
        # If no loop exists, create one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # If we're already in an async context, we need to use run_coroutine_threadsafe
            # For now, we'll use a simpler approach and make the tool async-compatible
            extracted = loop.run_until_complete(extractor.extract(text))
        else:
            extracted = loop.run_until_complete(extractor.extract(text))
        
        log_info("preferences_extracted_by_tool", user_id=user_id, extracted=extracted)
        
        # Update the profile with extracted preferences
        storage = _get_storage()
        profile = storage.load_profile(user_id)
        
        if extracted.get("favorite_genres"):
            for genre in extracted["favorite_genres"]:
                profile.add_favorite_genre(genre)
        
        if extracted.get("disliked_genres"):
            for genre in extracted["disliked_genres"]:
                profile.add_disliked_genre(genre)
        
        if extracted.get("favorite_artists"):
            for artist in extracted["favorite_artists"]:
                profile.add_favorite_artist(artist)
        
        if extracted.get("location"):
            profile.location = extracted["location"]
        
        storage.save_profile(profile)
        
        log_info("profile_updated_after_extraction", user_id=user_id)
        
        return profile.model_dump()
        
    except Exception as e:
        log_error("preference_extraction_failed_in_tool", user_id=user_id, error=str(e))
        # Return existing profile without changes
        storage = _get_storage()
        profile = storage.load_profile(user_id)
        return profile.model_dump()
