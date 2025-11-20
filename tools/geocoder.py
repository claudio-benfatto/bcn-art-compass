"""
Geocoder MCP Tool - mock geocoding for location queries.

This is a mock tool for Milestone 4 that returns sample coordinates
for location-based queries. In production, this would call a real
geocoding API like Google Maps, Mapbox, or Nominatim.
"""

from typing import Optional

from observability import log_info


class GeocoderTool:
    """
    Mock geocoder tool for location-based queries.

    Returns sample coordinates for testing location-aware features.
    """

    # Mock database of Barcelona locations
    LOCATIONS = {
        "barcelona": {"lat": 41.3851, "lon": 2.1734, "name": "Barcelona, Spain"},
        "gràcia": {"lat": 41.4036, "lon": 2.1574, "name": "Gràcia, Barcelona"},
        "gracia": {"lat": 41.4036, "lon": 2.1574, "name": "Gràcia, Barcelona"},
        "eixample": {"lat": 41.3888, "lon": 2.1590, "name": "Eixample, Barcelona"},
        "gothic quarter": {"lat": 41.3825, "lon": 2.1769, "name": "Gothic Quarter, Barcelona"},
        "el born": {"lat": 41.3839, "lon": 2.1831, "name": "El Born, Barcelona"},
        "born": {"lat": 41.3839, "lon": 2.1831, "name": "El Born, Barcelona"},
        "raval": {"lat": 41.3794, "lon": 2.1675, "name": "El Raval, Barcelona"},
        "barceloneta": {"lat": 41.3794, "lon": 2.1906, "name": "Barceloneta, Barcelona"},
        "montjuïc": {"lat": 41.3641, "lon": 2.1659, "name": "Montjuïc, Barcelona"},
        "montjuic": {"lat": 41.3641, "lon": 2.1659, "name": "Montjuïc, Barcelona"},
        "poble sec": {"lat": 41.3723, "lon": 2.1646, "name": "Poble Sec, Barcelona"},
        # Museums and venues
        "macba": {"lat": 41.3830, "lon": 2.1667, "name": "MACBA (Contemporary Art Museum)"},
        "picasso museum": {"lat": 41.3851, "lon": 2.1806, "name": "Picasso Museum"},
        "fundació miró": {"lat": 41.3688, "lon": 2.1598, "name": "Fundació Joan Miró"},
        "miro": {"lat": 41.3688, "lon": 2.1598, "name": "Fundació Joan Miró"},
        "caixaforum": {"lat": 41.3710, "lon": 2.1504, "name": "CaixaForum Barcelona"},
        "palau de la musica": {"lat": 41.3876, "lon": 2.1753, "name": "Palau de la Música Catalana"},
    }

    def __init__(self):
        """Initialize the geocoder tool."""
        log_info("geocoder_tool_initialized", locations=len(self.LOCATIONS))

    def geocode(self, location: str) -> Optional[dict]:
        """
        Get coordinates for a location string.

        Args:
            location: Location name or address

        Returns:
            Dict with 'lat', 'lon', and 'name' keys, or None if not found

        Example:
            >>> geocoder = GeocoderTool()
            >>> result = geocoder.geocode("Gràcia")
            >>> result
            {'lat': 41.4036, 'lon': 2.1574, 'name': 'Gràcia, Barcelona'}
        """
        location_lower = location.lower().strip()

        log_info("geocoding_request", location=location)

        # Direct lookup
        if location_lower in self.LOCATIONS:
            result = self.LOCATIONS[location_lower]
            log_info("geocoding_success", location=location, coordinates=result)
            return result

        # Partial match
        for key, value in self.LOCATIONS.items():
            if location_lower in key or key in location_lower:
                log_info("geocoding_partial_match", location=location, matched_key=key)
                return value

        # Default to Barcelona center if no match
        log_info("geocoding_fallback", location=location)
        return self.LOCATIONS["barcelona"]

    def reverse_geocode(self, lat: float, lon: float) -> dict:
        """
        Get location name from coordinates (reverse geocoding).

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dict with location information

        Example:
            >>> geocoder = GeocoderTool()
            >>> result = geocoder.reverse_geocode(41.3851, 2.1734)
            >>> result['name']
            'Barcelona, Spain'
        """
        log_info("reverse_geocoding_request", lat=lat, lon=lon)

        # Find closest location (simple distance calculation)
        min_dist = float("inf")
        closest = self.LOCATIONS["barcelona"]

        for location_data in self.LOCATIONS.values():
            dist = (
                (lat - location_data["lat"]) ** 2 + (lon - location_data["lon"]) ** 2
            ) ** 0.5
            if dist < min_dist:
                min_dist = dist
                closest = location_data

        log_info("reverse_geocoding_success", result=closest["name"])
        return closest

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate approximate distance between two coordinates in kilometers.

        Uses simple Euclidean distance for mock purposes.
        In production, use Haversine formula for accurate distances.

        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate

        Returns:
            Distance in kilometers (approximate)
        """
        # Rough conversion: 1 degree ≈ 111 km at equator
        lat_dist = (lat2 - lat1) * 111
        lon_dist = (lon2 - lon1) * 111 * 0.73  # Adjust for Barcelona's latitude

        distance = (lat_dist**2 + lon_dist**2) ** 0.5

        log_info(
            "distance_calculated",
            lat1=lat1,
            lon1=lon1,
            lat2=lat2,
            lon2=lon2,
            distance_km=round(distance, 2),
        )

        return distance


# Singleton instance for easy access
geocoder_tool = GeocoderTool()
