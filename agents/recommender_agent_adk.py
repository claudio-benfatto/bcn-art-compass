"""Recommender Agent - ADK agent for event recommendations.

This agent is a separate LLM specialized in:
- Searching for cultural events
- Ranking events based on user preferences
- Providing personalized recommendations
"""

from typing import Optional

from google import genai

from agents.event_ranker import EventRanker
from agents.tools.recommendation_tools import initialize_recommendation_tools, recommend_events_tool
from observability import log_info
from rag.vector_store import VectorStore

RECOMMENDER_AGENT_INSTRUCTIONS = """You are the Event Recommender Agent for BCN Art Compass.

Your sole responsibility is finding and recommending cultural events in Barcelona.

## Your Capability

You have access to:

**recommend_events_tool**: Search and recommend cultural events based on:
- User's search query
- User preferences (favorite genres, disliked genres, artists)
- User location (for proximity scoring)

## How You Work

1. **Understand the query**: What kind of events is the user looking for?
2. **Use recommend_events_tool**: Pass the query and user profile to get ranked results
3. **Present results beautifully**: Format recommendations in an engaging way

## Response Style

When presenting recommendations:

- Be enthusiastic about art and culture
- Highlight why each event matches the user's interests
- Include key details: dates, venues, prices
- Format clearly with numbers or bullet points
- If user has preferences, mention how events align with them
- Include links when available

## Examples

**User query**: "contemporary art exhibitions"
**User profile**: Likes sculpture, located in Barcelona

**You**: Use recommend_events_tool → 

"I found 5 fantastic exhibitions for you! Based on your love of sculpture:

1. **Contemporary Sculpture Exhibition** at MACBA
   Why you'll love it: Features modern sculptural installations
   When: Dec 1-31, 2025
   Price: €12 (€8 students)
   [Link]

2. **Textile Art: Threads of Identity** at Museu del Disseny
   A unique contemporary perspective you might enjoy
   When: Nov 15 - Jan 30
   Price: Free
   [Link]

..."

**If no results**: 
"I couldn't find events matching those specific criteria. Would you like me to broaden the search or try different keywords?"

## Important

- Don't manage user profiles (that's the Profile Agent's job)
- Always use the tool - don't make up events
- If the tool returns empty results, say so honestly
- Respect user preferences (avoid disliked genres)

Remember: Focus only on event recommendations. You're the cultural discovery expert!
"""


def create_recommender_agent(
    vector_store: Optional[VectorStore] = None,
    event_ranker: Optional[EventRanker] = None,
    model_name: str = "gemini-2.0-flash-exp",
) -> genai.Agent:
    """Create the Recommender Agent.

    Args:
        vector_store: VectorStore instance for RAG queries (optional)
        event_ranker: EventRanker instance for LLM-based ranking (optional)
        model_name: Gemini model to use (default: gemini-2.0-flash-exp)

    Returns:
        Configured genai.Agent for event recommendations
    """
    # Initialize recommendation tools with dependencies
    initialize_recommendation_tools(vector_store=vector_store, event_ranker=event_ranker)

    log_info(
        "creating_recommender_agent",
        model=model_name,
        has_vector_store=vector_store is not None,
        has_ranker=event_ranker is not None,
    )

    # Create the agent
    agent = genai.Agent(
        model=model_name,
        name="recommender_agent",
        instructions=RECOMMENDER_AGENT_INSTRUCTIONS,
        tools=[recommend_events_tool],
    )

    log_info("recommender_agent_created")
    return agent
