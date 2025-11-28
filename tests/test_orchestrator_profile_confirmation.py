"""Unit test for summarize_profile_update (deterministic formatting)."""

from agents.orchestrator import summarize_profile_update


def test_summarize_profile_update_basic():
    payload = {
        "profile": {"location": "barcelona"},
        "updated": {
            "favorite_genres_added": ["sculpture", "painting"],
            "favorite_genres_removed": ["video art"],
            "favorite_genres_not_found": ["digital"],
            "disliked_genres_added": [],
            "disliked_genres_removed": [],
            "disliked_genres_not_found": [],
            "favorite_artists_added": ["picasso"],
            "favorite_artists_removed": [],
            "favorite_artists_not_found": [],
            "location_changed": True,
        },
    }
    text = summarize_profile_update(payload)
    assert "Added sculpture, painting to favorite genres" in text
    assert "Removed video art from favorite genres" in text
    assert "Not found in favorite genres: digital" in text
    assert "Added picasso to favorite artists" in text
    assert "Location set to barcelona" in text

