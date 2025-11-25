"""Prompt templates for agent interactions.

Centralized location for all LLM prompts used throughout the application.
"""


def get_intent_detection_prompt(query: str) -> str:
    """
    Get the prompt for intent detection.

    Args:
        query: User query text

    Returns:
        Formatted prompt string for intent classification
    """
    return f"""Classify the user's intent into one of these categories:
- recommendation: User wants event/exhibition/museum recommendations or is searching for cultural activities
- preference_update: User is expressing likes, dislikes, preferences, or updating their profile
- general: General questions, greetings, or conversations not related to recommendations or preferences

Examples:
- "Show me contemporary art exhibitions" -> recommendation
- "I love sculpture" -> preference_update
- "What's the museum's address?" -> general
- "Find events this weekend" -> recommendation
- "I don't like video art" -> preference_update
- "Tell me about Picasso" -> general
- "Any good galleries near me?" -> recommendation
- "I'm interested in modern art" -> preference_update
- "Hello" -> general

User query: "{query}"

Respond with ONLY ONE WORD: recommendation, preference_update, or general"""


def get_preference_extraction_prompt(query: str) -> str:
    """
    Get the prompt for extracting user preferences.

    Args:
        query: User query text expressing preferences

    Returns:
        Formatted prompt string for preference extraction
    """
    return f"""You are a preference extraction assistant for a cultural events recommender system.

Analyze the following user statement and extract any preferences about:
- favorite_genres: Art/event genres they LIKE (contemporary art, sculpture, painting, etc.)
- disliked_genres: Art/event genres they DON'T like
- favorite_artists: Specific artists they mention favorably
- location: Location they mention (city, neighborhood)

User statement: "{query}"

Return ONLY a valid JSON object with these fields (use empty lists if nothing found):
{{
  "favorite_genres": [],
  "disliked_genres": [],
  "favorite_artists": [],
  "location": null
}}

Examples:
Input: "I don't like video art"
Output: {{"favorite_genres": [], "disliked_genres": ["video art"], "favorite_artists": [], "location": null}}

Input: "I love contemporary sculpture and Picasso"
Output: {{"favorite_genres": ["contemporary sculpture"], "disliked_genres": [], "favorite_artists": ["Picasso"], "location": null}}

Now analyze the user statement and return only the JSON object:"""
