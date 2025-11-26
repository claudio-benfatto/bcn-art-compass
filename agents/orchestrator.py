"""ADK-based Orchestrator Agent for BCN Art Compass.

This module provides the main orchestrator agent that coordinates all user interactions.
It uses Google's Agent Development Kit (ADK) with a multi-agent architecture:

- Orchestrator Agent: Routes queries and coordinates between specialized agents
- Profile Agent: Manages user preferences and profile data (separate LLM)
- Recommender Agent: Searches and recommends events (separate LLM)

Each agent is a separate Gemini model instance that can be called via AgentTool.
"""

from typing import Optional

from google import genai
from google.adk.tools import AgentTool
from google.genai import types

from agents.event_ranker import EventRanker
from agents.profile_agent_adk import create_profile_agent
from agents.prompts import ORCHESTRATOR_INSTRUCTIONS
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage_interface import ProfileStorage
from observability import log_error, log_info
from rag.vector_store import VectorStore


class ADKOrchestrator:
    """ADK-based orchestrator for the BCN Art Compass system.

    This orchestrator uses Google's Agent Development Kit to create a declarative agent
    that coordinates between profile management and event recommendation tools.

    The agent is configured with:
    - System instructions defining its behavior and personality
    - Tools for profile management and recommendations
    - Gemini model for natural language understanding
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        event_ranker: Optional[EventRanker] = None,
        storage: Optional[ProfileStorage] = None,
        model_name: str = "gemini-2.5-flash-exp",
    ):
        """Initialize the ADK orchestrator.

        Args:
            vector_store: VectorStore instance for RAG queries (optional)
            event_ranker: EventRanker instance for LLM-based ranking (optional)
            storage: ProfileStorage instance for user profiles (optional)
            model_name: Gemini model to use (default: gemini-2.5-flash-exp)
        """
        log_info(
            "adk_orchestrator_initializing",
            model=model_name,
            has_vector_store=vector_store is not None,
            has_ranker=event_ranker is not None,
        )

        # Create specialized sub-agents
        profile_agent = create_profile_agent(storage=storage, model_name=model_name)
        recommender_agent = create_recommender_agent(
            vector_store=vector_store,
            event_ranker=event_ranker,
            model_name=model_name,
        )

        # Create the orchestrator agent with sub-agents as tools
        self.agent = genai.Agent(
            model=model_name,
            name="orchestrator",
            instructions=ORCHESTRATOR_INSTRUCTIONS,
            tools=[
                AgentTool(agent=profile_agent),
                AgentTool(agent=recommender_agent),
            ],
        )

        log_info(
            "adk_orchestrator_initialized",
            orchestrator_agent=self.agent.name,
            sub_agents=["profile_agent", "recommender_agent"],
        )

    def chat(self, user_id: str, message: str, session_id: Optional[str] = None) -> str:
        """Process a user message and generate a response.

        This method:
        1. Creates a session context with the user_id
        2. Sends the message to the ADK agent
        3. The agent decides which tools to use (if any)
        4. Returns the agent's natural language response

        Args:
            user_id: Unique identifier for the user
            message: User's message text
            session_id: Optional session identifier for conversation continuity

        Returns:
            Agent's response text

        Example:
            >>> orchestrator = ADKOrchestrator()
            >>> response = orchestrator.chat("user123", "Show me contemporary art exhibitions")
            >>> print(response)
            "I found 5 great exhibitions for you! ..."
        """
        log_info("processing_user_message", user_id=user_id, message=message[:100], session_id=session_id)

        try:
            # Send message to agent with user context in system instruction
            # The agent will use sub-agents as needed and generate a response
            response = self.agent.generate_content(
                message,
                config=types.GenerateContentConfig(
                    system_instruction=f"User ID: {user_id}. Session ID: {session_id or user_id}.",
                    temperature=0.7,
                ),
            )

            response_text = response.text

            log_info(
                "chat_response_generated",
                user_id=user_id,
                response_length=len(response_text),
                session_id=session_id,
            )

            return response_text

        except Exception as e:
            log_error(
                "chat_error",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return (
                "I apologize, but I encountered an error while processing your request. "
                "Please try again or rephrase your question."
            )

    async def chat_async(self, user_id: str, message: str, session_id: Optional[str] = None) -> str:
        """Async version of chat for use in async contexts.

        Args:
            user_id: Unique identifier for the user
            message: User's message text
            session_id: Optional session identifier for conversation continuity

        Returns:
            Agent's response text
        """
        # For now, just call the sync version
        # TODO: Implement true async when ADK supports it
        return self.chat(user_id, message, session_id)


def create_orchestrator(
    vector_store: Optional[VectorStore] = None,
    event_ranker: Optional[EventRanker] = None,
    storage: Optional[ProfileStorage] = None,
    model_name: str = "gemini-2.0-flash-exp",
) -> ADKOrchestrator:
    """Factory function to create an ADK orchestrator.

    This is the recommended way to create an orchestrator instance.

    Args:
        vector_store: VectorStore instance for RAG queries (optional)
        event_ranker: EventRanker instance for LLM-based ranking (optional)
        storage: ProfileStorage instance for user profiles (optional)
        model_name: Gemini model to use (default: gemini-2.0-flash-exp)

    Returns:
        Configured ADKOrchestrator instance

    Example:
        >>> from rag.vector_store import VectorStore
        >>> from agents.event_ranker import EventRanker
        >>> from memory.storage import MemoryStorage
        >>>
        >>> orchestrator = create_orchestrator(
        ...     vector_store=VectorStore(),
        ...     event_ranker=EventRanker(),
        ...     storage=MemoryStorage()
        ... )
    """
    return ADKOrchestrator(
        vector_store=vector_store,
        event_ranker=event_ranker,
        storage=storage,
        model_name=model_name,
    )
