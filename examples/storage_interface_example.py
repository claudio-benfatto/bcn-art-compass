"""
Example: Using the ProfileStorage interface to switch between storage backends.

This demonstrates how the ProfileStorage protocol enables seamless switching
between JSON-based local storage and Firestore cloud storage without changing
application code.
"""

from memory import MemoryStorage, FirestoreStorage, ProfileStorage, UserProfile


def manage_user_preferences(storage: ProfileStorage, user_id: str):
    """
    Example function that works with any ProfileStorage implementation.
    
    This function can accept either MemoryStorage or FirestoreStorage
    (or any future storage backend that implements ProfileStorage).
    """
    # Load or create profile
    profile = storage.load_profile(user_id)
    print(f"Loaded profile for {user_id}")
    
    # Update preferences
    profile.add_favorite_genre("contemporary art")
    profile.add_favorite_artist("Antoni Gaudí")
    profile.location = "Barcelona, Spain"
    
    # Save changes
    storage.save_profile(profile)
    print(f"Saved preferences for {user_id}")
    
    # Verify
    if storage.profile_exists(user_id):
        print(f"✓ Profile exists in storage")
    
    return profile


if __name__ == "__main__":
    # Example 1: Use local JSON storage (development)
    print("=== Using MemoryStorage (local JSON) ===")
    local_storage = MemoryStorage("storage/example_profiles.json")
    profile1 = manage_user_preferences(local_storage, "user123")
    print(f"Favorites: {profile1.favorite_genres}")
    print(f"Location: {profile1.location}")
    print()
    
    # Example 2: Use Firestore (production)
    # Uncomment to use real Firestore:
    # print("=== Using FirestoreStorage (cloud) ===")
    # cloud_storage = FirestoreStorage(
    #     collection_name="user_profiles",
    #     project_id="bcn-art-compass"
    # )
    # profile2 = manage_user_preferences(cloud_storage, "user456")
    # print(f"Favorites: {profile2.favorite_genres}")
    # print(f"Location: {profile2.location}")
    
    print("✓ Same code works with both storage backends!")
