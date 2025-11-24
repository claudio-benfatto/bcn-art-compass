"""
Pydantic models for events and venues.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Event model matching the YAML structure."""

    id: str
    title: str
    description: str
    genres: list[str]
    artists: list[str]
    venue_id: str
    start_date: date
    end_date: date
    opening_hours: str
    url: str
    booking_url: Optional[str] = None
    cost_range: str
    accessibility_notes: Optional[str] = None
    tags: list[str]


class Venue(BaseModel):
    """Venue model matching the YAML structure."""

    id: str
    name: str
    description: str
    address: str
    latitude: float
    longitude: float
    neighborhood: str
    type: str
    website_url: Optional[str] = None
    opening_hours: str
    price_range: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    tags: list[str]
    accessibility_notes: Optional[str] = None


class EventWithVenue(BaseModel):
    """Combined event and venue information for RAG indexing."""

    event: Event
    venue: Venue

    def to_text(self) -> str:
        """
        Convert event and venue to searchable text for embedding.

        Returns:
            A formatted string containing all relevant information
        """
        text_parts = [
            f"Event: {self.event.title}",
            f"Description: {self.event.description}",
            f"Genres: {', '.join(self.event.genres)}",
            f"Artists: {', '.join(self.event.artists)}",
            f"Tags: {', '.join(self.event.tags)}",
            f"Venue: {self.venue.name}",
            f"Location: {self.venue.neighborhood}, Barcelona",
            f"Venue Type: {self.venue.type}",
            f"Venue Description: {self.venue.description}",
            f"Dates: {self.event.start_date} to {self.event.end_date}",
            f"Cost: {self.event.cost_range}",
        ]

        return "\n".join(text_parts)


class SearchResult(BaseModel):
    """Search result from RAG query."""

    event_id: str
    title: str
    description: str
    venue_name: str
    genres: list[str]
    start_date: date
    end_date: date
    cost_range: str
    score: float = Field(description="Similarity score from vector search")
    url: str
    venue_latitude: float | None = Field(None, description="Venue latitude for location-based scoring")
    venue_longitude: float | None = Field(None, description="Venue longitude for location-based scoring")
