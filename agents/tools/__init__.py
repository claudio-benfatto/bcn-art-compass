"""ADK tools for the BCN Art Compass multi-agent system.

This module contains tool factory functions that use closure pattern for dependency injection.
Tools are created by calling factory functions with required dependencies.
"""

from agents.tools.distance_tools import (
    calculate_distances_tool,
    calculate_single_distance_tool,
)
from agents.tools.profile_tools import create_profile_tools
from agents.tools.recommendation_tools import create_recommendation_tools

__all__ = [
    "create_profile_tools",
    "create_recommendation_tools",
    "calculate_distances_tool",
    "calculate_single_distance_tool",
]
