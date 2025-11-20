"""
Pydantic models for user profiles and memory.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """
    User profile with preferences and metadata.

    Stores long-term memory about user preferences for personalized recommendations.
    """

    user_id: str = Field(..., description="Unique user identifier")
    location: Optional[str] = Field(None, description="User's location (city, neighborhood, etc.)")
    favorite_genres: list[str] = Field(default_factory=list, description="Genres user likes")
    disliked_genres: list[str] = Field(default_factory=list, description="Genres user dislikes")
    favorite_artists: list[str] = Field(default_factory=list, description="Artists user likes")
    preferred_distance_km: Optional[float] = Field(
        None,
        description="Maximum distance in km user wants to travel",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Profile creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Profile last update timestamp",
    )

    def add_favorite_genre(self, genre: str) -> None:
        """Add a genre to favorites if not already present."""
        if genre and genre not in self.favorite_genres:
            self.favorite_genres.append(genre)
            self.updated_at = datetime.utcnow().isoformat()

    def add_disliked_genre(self, genre: str) -> None:
        """Add a genre to dislikes if not already present."""
        if genre and genre not in self.disliked_genres:
            self.disliked_genres.append(genre)
            self.updated_at = datetime.utcnow().isoformat()

    def add_favorite_artist(self, artist: str) -> None:
        """Add an artist to favorites if not already present."""
        if artist and artist not in self.favorite_artists:
            self.favorite_artists.append(artist)
            self.updated_at = datetime.utcnow().isoformat()

    def remove_favorite_genre(self, genre: str) -> None:
        """Remove a genre from favorites."""
        if genre in self.favorite_genres:
            self.favorite_genres.remove(genre)
            self.updated_at = datetime.utcnow().isoformat()

    def remove_disliked_genre(self, genre: str) -> None:
        """Remove a genre from dislikes."""
        if genre in self.disliked_genres:
            self.disliked_genres.remove(genre)
            self.updated_at = datetime.utcnow().isoformat()

    def remove_favorite_artist(self, artist: str) -> None:
        """Remove an artist from favorites."""
        if artist in self.favorite_artists:
            self.favorite_artists.remove(artist)
            self.updated_at = datetime.utcnow().isoformat()
