#!/usr/bin/env python3
"""Quick test of preference extraction."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.profile_agent import ProfileAgent
from memory.storage import MemoryStorage


async def test_extraction():
    """Test preference extraction with a simple statement."""
    # Setup
    storage = MemoryStorage("storage/test_profiles.json")
    agent = ProfileAgent(storage=storage)
    
    test_user = "test_extraction_user"
    test_statement = "I love contemporary art and sculpture"
    
    print(f"\n🧪 Testing preference extraction")
    print(f"Statement: '{test_statement}'")
    print("-" * 60)
    
    # Extract
    profile = await agent.extract_preferences(test_user, test_statement)
    
    print(f"\n📊 Results:")
    print(f"Favorite genres: {profile.favorite_genres}")
    print(f"Disliked genres: {profile.disliked_genres}")
    print(f"Favorite artists: {profile.favorite_artists}")
    print(f"Location: {profile.location}")
    print("-" * 60)
    
    # Cleanup
    storage.delete_profile(test_user)


if __name__ == "__main__":
    if "GOOGLE_API_KEY" not in os.environ:
        print("❌ GOOGLE_API_KEY not set")
        sys.exit(1)
    
    asyncio.run(test_extraction())
