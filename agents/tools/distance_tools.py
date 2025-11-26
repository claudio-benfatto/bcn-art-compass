"""Distance calculation tools for event recommendations.

These tools calculate distances between user coordinates and event venues,
supporting both single and batch operations for efficiency.

Best Practices Implemented:
- Clear, descriptive function names and docstrings
- Specific parameter types (float, not Any)
- Return structured data (dict with clear keys)
- Graceful error handling for missing coordinates
- Human-readable categories in addition to numeric values
- Logging for observability
"""

from math import asin, cos, radians, sin, sqrt
from typing import Any

from observability import log_error, log_info


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates using Haversine formula.

    The Haversine formula calculates the great-circle distance between two points
    on a sphere given their longitudes and latitudes. This is more accurate than
    simple Euclidean distance for geographic coordinates.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance in kilometers (rounded to 2 decimal places)
    """
    try:
        # Convert to radians
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(
            radians, [lat1, lon1, lat2, lon2]
        )

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Radius of earth in kilometers
        r = 6371

        return round(c * r, 2)
    except Exception as e:
        log_error("haversine_calculation_failed", error=str(e))
        return 0.0


def _categorize_distance(distance_km: float) -> str:
    """Categorize distance into human-readable categories.

    Args:
        distance_km: Distance in kilometers

    Returns:
        Category string: "nearby", "walkable", "transit", or "far"
    """
    if distance_km < 1.0:
        return "nearby"  # < 1km: walking distance
    elif distance_km < 3.0:
        return "walkable"  # 1-3km: comfortable walk
    elif distance_km < 10.0:
        return "transit"  # 3-10km: public transit recommended
    else:
        return "far"  # > 10km: requires planning


def calculate_distances_tool(
    user_latitude: float,
    user_longitude: float,
    event_coordinates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Calculate distances between user location and multiple event venues.

    This tool uses the Haversine formula to calculate accurate geographic distances
    between the user's location and a batch of event venues. This is useful for
    ranking events by proximity and helping users find nearby cultural activities.

    Args:
        user_latitude: User's latitude coordinate
        user_longitude: User's longitude coordinate
        event_coordinates: List of event location dictionaries, each containing:
            - event_id: Unique identifier for the event
            - latitude: Event venue latitude
            - longitude: Event venue longitude
            - title: Event title (optional, for logging)

    Returns:
        List of dictionaries with distance information for each event:
        - event_id: Event identifier (matches input)
        - distance_km: Distance in kilometers (rounded to 2 decimals)
        - distance_category: Human-readable category ("nearby", "walkable", "transit", "far")

    Example:
        >>> distances = calculate_distances_tool(
        ...     user_latitude=41.3851,
        ...     user_longitude=2.1734,
        ...     event_coordinates=[
        ...         {"event_id": "evt1", "latitude": 41.3830, "longitude": 2.1667, "title": "MACBA"},
        ...         {"event_id": "evt2", "latitude": 41.3851, "longitude": 2.1806, "title": "Picasso"},
        ...     ]
        ... )
        >>> distances[0]["distance_km"]
        0.68
        >>> distances[0]["distance_category"]
        "nearby"
    """
    log_info(
        "calculating_batch_distances",
        user_coords=(user_latitude, user_longitude),
        num_events=len(event_coordinates),
    )

    results = []

    for event_coord in event_coordinates:
        event_id = event_coord.get("event_id")
        event_lat = event_coord.get("latitude")
        event_lon = event_coord.get("longitude")
        event_title = event_coord.get("title", "Unknown")

        # Skip if coordinates are missing
        if event_lat is None or event_lon is None:
            log_info("skipping_event_no_coordinates", event_id=event_id, title=event_title)
            results.append(
                {
                    "event_id": event_id,
                    "distance_km": None,
                    "distance_category": "unknown",
                }
            )
            continue

        # Calculate distance using Haversine
        distance_km = _haversine_distance(
            user_latitude, user_longitude, event_lat, event_lon
        )

        # Categorize distance
        category = _categorize_distance(distance_km)

        log_info(
            "distance_calculated",
            event_id=event_id,
            title=event_title,
            distance_km=distance_km,
            category=category,
        )

        results.append(
            {
                "event_id": event_id,
                "distance_km": distance_km,
                "distance_category": category,
            }
        )

    log_info("batch_distances_complete", num_results=len(results))

    return results


def calculate_single_distance_tool(
    user_latitude: float,
    user_longitude: float,
    event_latitude: float,
    event_longitude: float,
) -> dict[str, Any]:
    """Calculate distance between user location and a single event venue.

    Convenience wrapper for single distance calculations. For multiple events,
    use calculate_distances_tool for better performance.

    Args:
        user_latitude: User's latitude coordinate
        user_longitude: User's longitude coordinate
        event_latitude: Event venue latitude
        event_longitude: Event venue longitude

    Returns:
        Dictionary with distance information:
        - distance_km: Distance in kilometers (rounded to 2 decimals)
        - distance_category: Human-readable category

    Example:
        >>> distance = calculate_single_distance_tool(41.3851, 2.1734, 41.3830, 2.1667)
        >>> distance["distance_km"]
        0.68
    """
    results = calculate_distances_tool(
        user_latitude=user_latitude,
        user_longitude=user_longitude,
        event_coordinates=[
            {
                "event_id": "single",
                "latitude": event_latitude,
                "longitude": event_longitude,
            }
        ],
    )

    return {
        "distance_km": results[0]["distance_km"],
        "distance_category": results[0]["distance_category"],
    }
