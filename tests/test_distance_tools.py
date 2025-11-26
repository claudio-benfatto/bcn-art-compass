"""Tests for distance calculation tools."""

import pytest

from agents.tools.distance_tools import (
    _haversine_distance,
    calculate_distances_tool,
    calculate_single_distance_tool,
)


def test_haversine_distance_same_location():
    """Test Haversine distance returns 0 for same location."""
    distance = _haversine_distance(41.3851, 2.1734, 41.3851, 2.1734)
    assert distance == pytest.approx(0.0, abs=0.01)


def test_haversine_distance_known_locations():
    """Test Haversine distance between known Barcelona locations.

    MACBA to Picasso Museum is approximately 2.5 km in real world.
    """
    # MACBA coordinates
    macba_lat, macba_lon = 41.3830, 2.1667
    # Picasso Museum coordinates
    picasso_lat, picasso_lon = 41.3851, 2.1806

    distance = _haversine_distance(macba_lat, macba_lon, picasso_lat, picasso_lon)

    # Should be around 1.3 km (straight line distance)
    assert 1.0 < distance < 2.0


def test_calculate_single_distance_tool():
    """Test single distance calculation tool."""
    # User in Eixample
    user_lat, user_lon = 41.3917, 2.1649
    # MACBA
    event_lat, event_lon = 41.3830, 2.1667

    result = calculate_single_distance_tool(user_lat, user_lon, event_lat, event_lon)

    assert "distance_km" in result
    assert "distance_category" in result
    assert result["distance_km"] > 0
    assert result["distance_category"] in ["nearby", "walkable", "transit", "far"]


def test_calculate_distances_tool_batch():
    """Test batch distance calculation tool."""
    # User in center of Barcelona
    user_lat, user_lon = 41.3851, 2.1734

    event_coordinates = [
        {
            "event_id": "evt1",
            "latitude": 41.3830,
            "longitude": 2.1667,
            "title": "MACBA",
        },
        {
            "event_id": "evt2",
            "latitude": 41.3851,
            "longitude": 2.1806,
            "title": "Picasso Museum",
        },
        {
            "event_id": "evt3",
            "latitude": 41.3587,
            "longitude": 2.1860,
            "title": "Fundació Miró",
        },
    ]

    results = calculate_distances_tool(user_lat, user_lon, event_coordinates)

    # Should return results for all events
    assert len(results) == 3

    # Check structure of each result
    for result in results:
        assert "event_id" in result
        assert "distance_km" in result
        assert "distance_category" in result
        assert result["distance_km"] is not None
        assert result["distance_category"] in ["nearby", "walkable", "transit", "far"]

    # Check event IDs match
    event_ids = [r["event_id"] for r in results]
    assert "evt1" in event_ids
    assert "evt2" in event_ids
    assert "evt3" in event_ids


def test_calculate_distances_tool_missing_coordinates():
    """Test batch tool handles missing coordinates gracefully."""
    user_lat, user_lon = 41.3851, 2.1734

    event_coordinates = [
        {
            "event_id": "evt1",
            "latitude": 41.3830,
            "longitude": 2.1667,
            "title": "Valid Event",
        },
        {
            "event_id": "evt2",
            "latitude": None,
            "longitude": None,
            "title": "Missing Coordinates",
        },
        {
            "event_id": "evt3",
            "latitude": 41.3587,
            "longitude": 2.1860,
            "title": "Another Valid Event",
        },
    ]

    results = calculate_distances_tool(user_lat, user_lon, event_coordinates)

    # Should return results for all events
    assert len(results) == 3

    # Event with missing coordinates should have None distance
    evt2_result = next(r for r in results if r["event_id"] == "evt2")
    assert evt2_result["distance_km"] is None
    assert evt2_result["distance_category"] == "unknown"

    # Valid events should have distances
    evt1_result = next(r for r in results if r["event_id"] == "evt1")
    assert evt1_result["distance_km"] is not None
    assert evt1_result["distance_category"] != "unknown"


def test_distance_categories():
    """Test distance categorization thresholds."""
    user_lat, user_lon = 41.3851, 2.1734

    # Create test events at specific distances
    # nearby: < 1km
    # walkable: 1-3km
    # transit: 3-10km
    # far: > 10km

    event_coordinates = [
        {
            "event_id": "nearby",
            "latitude": 41.3860,
            "longitude": 2.1740,  # ~0.1 km
        },
        {
            "event_id": "walkable",
            "latitude": 41.4000,
            "longitude": 2.1800,  # ~1.8 km
        },
        {
            "event_id": "transit",
            "latitude": 41.4200,
            "longitude": 2.2000,  # ~5 km
        },
        {
            "event_id": "far",
            "latitude": 41.5000,
            "longitude": 2.3000,  # ~15 km
        },
    ]

    results = calculate_distances_tool(user_lat, user_lon, event_coordinates)

    # Check categories
    nearby_result = next(r for r in results if r["event_id"] == "nearby")
    assert nearby_result["distance_category"] == "nearby"

    walkable_result = next(r for r in results if r["event_id"] == "walkable")
    assert walkable_result["distance_category"] == "walkable"

    transit_result = next(r for r in results if r["event_id"] == "transit")
    assert transit_result["distance_category"] == "transit"

    far_result = next(r for r in results if r["event_id"] == "far")
    assert far_result["distance_category"] == "far"


def test_calculate_distances_tool_empty_list():
    """Test batch tool with empty event list."""
    user_lat, user_lon = 41.3851, 2.1734
    event_coordinates = []

    results = calculate_distances_tool(user_lat, user_lon, event_coordinates)

    assert len(results) == 0
