#!/usr/bin/env python3
"""
Demo script for Milestone 3: Preference Extraction and Personalization.

This demonstrates:
1. Initial recommendation query (no preferences)
2. User expresses preference (dislike)
3. Profile is updated and persisted
4. New recommendation query reflects the preference

Usage:
    python scripts/demo_preferences.py

Note: This demo uses mocked LLM responses to avoid API costs.
For real usage with Google Gemini, set the GOOGLE_API_KEY environment variable.
"""

import asyncio
import json
from unittest.mock import MagicMock

from agents.orchestrator import OrchestratorAgent
from agents.profile_agent import ProfileAgent
from memory.storage import MemoryStorage


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def main():
    """Run the preference extraction demo."""
    print_section("Milestone 3: Preference Extraction Demo")

    # Setup
    user_id = "demo_user"
    storage = MemoryStorage("storage/demo_profiles.json")
    profile_agent = ProfileAgent(storage=storage)

    # Clean up any existing demo profile
    if storage.profile_exists(user_id):
        storage.delete_profile(user_id)
        print(f"✓ Cleaned up existing profile for {user_id}\n")

    # Create orchestrator with local embeddings (zero-cost)
    orchestrator = OrchestratorAgent(
        profile_agent=profile_agent,
        use_local_embeddings=True,
    )

    # Mock the Gemini model to avoid API costs
    mock_model = MagicMock()
    orchestrator.profile_agent.model = mock_model
    print("✓ Using mocked LLM (no API costs)\n")

    # Step 1: Initial recommendation query (no preferences yet)
    print_section("Step 1: Initial Recommendation Query (No Preferences)")
    query1 = "Show me contemporary art exhibitions"
    print(f"User: {query1}")
    print("\nProfile status: No preferences yet")
    print()

    response1 = await orchestrator.process_query(query1, user_id=user_id)
    print(f"System:\n{response1}\n")

    # Step 2: User expresses a dislike
    print_section("Step 2: User Expresses Preference")
    query2 = "I don't like video art"
    print(f"User: {query2}")
    print()

    # Mock the LLM response for preference extraction
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "favorite_genres": [],
        "disliked_genres": ["video art"],
        "favorite_artists": [],
        "location": None,
    })
    mock_model.generate_content.return_value = mock_response

    response2 = await orchestrator.process_query(query2, user_id=user_id)
    print(f"System:\n{response2}\n")

    # Step 3: Verify profile update
    print_section("Step 3: Profile Verification")
    profile = profile_agent.load_profile(user_id)
    print("Profile contents:")
    print(f"  User ID: {profile.user_id}")
    print(f"  Favorite genres: {profile.favorite_genres}")
    print(f"  Disliked genres: {profile.disliked_genres}")
    print(f"  Favorite artists: {profile.favorite_artists}")
    print(f"  Location: {profile.location}")
    print(f"  Created: {profile.created_at}")
    print(f"  Updated: {profile.updated_at}")
    print()

    # Step 4: Verify persistence
    print("Testing persistence (reload from storage)...")
    reloaded = storage.load_profile(user_id)
    assert reloaded.disliked_genres == profile.disliked_genres
    print("✓ Profile successfully persisted to storage\n")

    # Step 5: Another recommendation query
    print_section("Step 4: New Recommendation Query (With Preferences)")
    query3 = "Find me interesting exhibitions"
    print(f"User: {query3}")
    print("\nProfile status: Dislikes video art")
    print("Expected: Video art events will be penalized in ranking\n")

    response3 = await orchestrator.process_query(query3, user_id=user_id)
    print(f"System:\n{response3}\n")

    # Step 6: Add a positive preference
    print_section("Step 5: Adding a Positive Preference")
    query4 = "I love contemporary sculpture"
    print(f"User: {query4}")
    print()

    # Mock another LLM response
    mock_response2 = MagicMock()
    mock_response2.text = json.dumps({
        "favorite_genres": ["contemporary sculpture"],
        "disliked_genres": [],
        "favorite_artists": [],
        "location": None,
    })
    mock_model.generate_content.return_value = mock_response2

    response4 = await orchestrator.process_query(query4, user_id=user_id)
    print(f"System:\n{response4}\n")

    # Final profile status
    print_section("Final Profile Status")
    final_profile = profile_agent.load_profile(user_id)
    print("Complete profile:")
    print(f"  Favorite genres: {final_profile.favorite_genres}")
    print(f"  Disliked genres: {final_profile.disliked_genres}")
    print()

    print_section("Demo Complete!")
    print("Key takeaways:")
    print("  ✓ Users can express preferences in natural language")
    print("  ✓ LLM extracts structured preferences from free text")
    print("  ✓ Preferences persist across sessions")
    print("  ✓ Future recommendations are personalized based on profile")
    print("  ✓ Both likes and dislikes are tracked")
    print()

    # Example output for documentation
    print_section("Example Real Conversation Flow")
    print("""
User: "Show me contemporary art exhibitions"
System: [Returns recommendations based on query only]

User: "I don't like video art"
System: "Got it! I've updated your preferences. You now have 0 favorite
         genre(s) and 1 disliked genre(s). Your future recommendations
         will reflect these preferences!"

User: "Find me interesting exhibitions"
System: [Returns recommendations, video art events ranked lower]

User: "I love contemporary sculpture"
System: "Got it! I've updated your preferences. You now have 1 favorite
         genre(s) and 1 disliked genre(s). Your future recommendations
         will reflect these preferences!"

User: "What's happening this weekend?"
System: [Returns recommendations, sculpture events ranked higher,
         video art ranked lower]
    """)


if __name__ == "__main__":
    asyncio.run(main())
