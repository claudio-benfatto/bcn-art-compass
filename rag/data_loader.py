"""
Data loading utilities for events and venues from YAML files.
"""

from pathlib import Path
from typing import Optional

import yaml

from observability import log_info
from rag.models import Event, EventWithVenue, Venue


def load_events(file_path: Optional[str] = None) -> list[Event]:
    """
    Load events from YAML file.

    Args:
        file_path: Path to events.yaml. If None, uses default data/events.yaml

    Returns:
        List of Event objects
    """
    if file_path is None:
        file_path = str(Path(__file__).parent.parent / "data" / "events.yaml")

    log_info("loading_events", file_path=file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    events = [Event(**event_data) for event_data in data["events"]]

    log_info("events_loaded", count=len(events))
    return events


def load_venues(file_path: Optional[str] = None) -> list[Venue]:
    """
    Load venues from YAML file.

    Args:
        file_path: Path to venues.yaml. If None, uses default data/venues.yaml

    Returns:
        List of Venue objects
    """
    if file_path is None:
        file_path = str(Path(__file__).parent.parent / "data" / "venues.yaml")

    log_info("loading_venues", file_path=file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    venues = [Venue(**venue_data) for venue_data in data["venues"]]

    log_info("venues_loaded", count=len(venues))
    return venues


def load_events_with_venues(
    events_file: Optional[str] = None,
    venues_file: Optional[str] = None,
) -> list[EventWithVenue]:
    """
    Load events and join with their venues.

    Args:
        events_file: Path to events.yaml
        venues_file: Path to venues.yaml

    Returns:
        List of EventWithVenue objects
    """
    events = load_events(events_file)
    venues = load_venues(venues_file)

    # Create venue lookup dict
    venue_map = {venue.id: venue for venue in venues}

    # Join events with venues
    events_with_venues = []
    for event in events:
        venue = venue_map.get(event.venue_id)
        if venue:
            events_with_venues.append(EventWithVenue(event=event, venue=venue))
        else:
            log_info("venue_not_found_for_event", event_id=event.id, venue_id=event.venue_id, level="warning")

    log_info("events_with_venues_loaded", count=len(events_with_venues))
    return events_with_venues
