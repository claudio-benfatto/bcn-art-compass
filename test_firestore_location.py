import asyncio
from agents.profile_agent import ProfileAgent
from memory.storage_firestore import FirestoreStorage

async def test():
    # Use Firestore
    storage = FirestoreStorage()
    agent = ProfileAgent(storage=storage)
    
    # Test extracting location
    print("Testing: 'I love sculpture. I live in Gràcia'")
    profile = await agent.extract_preferences(
        "test_location_user",
        "I love sculpture. I live in Gràcia"
    )
    
    print(f"\nExtracted profile:")
    print(f"  Genres: {profile.favorite_genres}")
    print(f"  Location: {profile.location}")
    
    # Load it back
    print("\nLoading profile back...")
    loaded = storage.load_profile("test_location_user")
    print(f"  Genres: {loaded.favorite_genres}")
    print(f"  Location: {loaded.location}")
    
    # Now try to use it in a recommendation
    print("\nTrying recommendation with loaded profile...")
    from agents.recommender_agent import RecommenderAgent
    recommender = RecommenderAgent()
    try:
        results = recommender.recommend("Show me art", profile=loaded, k=3)
        print(f"  Got {len(results)} recommendations")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
