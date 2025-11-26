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
from google.adk import Agent
from google.adk.apps.app import EventsCompactionConfig
from google.adk.sessions import DatabaseSessionService
from google.adk.tools import AgentTool
from google.genai import types

from agents.prompts import ORCHESTRATOR_INSTRUCTIONS
from observability import log_error, log_info


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
        profile_agent: Agent,
        recommender_agent: Agent,
        model_name: str = "gemini-2.5-flash-exp",
        database_url: Optional[str] = None,
        compaction_interval: int = 5,
        overlap_size: int = 2,
    ):
        """Initialize the ADK orchestrator.

        Args:
            profile_agent: Pre-initialized Profile Agent (required)
            recommender_agent: Pre-initialized Recommender Agent (required)
            model_name: Gemini model to use for orchestrator (default: gemini-2.5-flash-exp)
            database_url: Optional database URL for session persistence
                         (e.g., "sqlite:///sessions.db" or Firestore URL)
                         If None, uses in-memory storage (not suitable for production)
            compaction_interval: Number of turns before triggering conversation compaction
                                (default: 5, helps manage token limits)
            overlap_size: Number of previous turns to keep for context during compaction
                         (default: 2, maintains conversation continuity)
        """
        log_info(
            "adk_orchestrator_initializing",
            model=model_name,
            profile_agent_name=profile_agent.name,
            recommender_agent_name=recommender_agent.name,
            has_database=database_url is not None,
            compaction_interval=compaction_interval,
            overlap_size=overlap_size,
        )

        # Store compaction configuration
        self._compaction_interval = compaction_interval
        self._overlap_size = overlap_size

        # Create compaction config for conversation history management
        compaction_config = EventsCompactionConfig(
            compaction_interval=compaction_interval,
            overlap_size=overlap_size,
        )

        # Initialize session service for persistent conversation history
        self._session_service = DatabaseSessionService(
            db_url=database_url or ":memory:",
            events_compaction_config=compaction_config,
        )
        log_info(
            "session_service_initialized",
            database_url=database_url or "in-memory",
            compaction_enabled=True,
            compaction_interval=compaction_interval,
            overlap_size=overlap_size,
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
        1. Retrieves or creates a session for conversation history
        2. Adds the user message to the session history
        3. Sends the message with history to the ADK agent
        4. The agent decides which tools to use (if any)
        5. Saves the updated conversation history to the session service
        6. Returns the agent's natural language response

        Args:
            user_id: Unique identifier for the user
            message: User's message text
            session_id: Optional session identifier for conversation continuity
                       (defaults to user_id if not provided)

        Returns:
            Agent's response text

        Example:
            >>> orchestrator = ADKOrchestrator()
            >>> response = orchestrator.chat("user123", "Show me contemporary art exhibitions")
            >>> print(response)
            "I found 5 great exhibitions for you! ..."
        """
        # Use user_id as session_id if not provided
        session_id = session_id or user_id

        log_info(
            "processing_user_message",
            user_id=user_id,
            message=message[:100],
            session_id=session_id,
        )

        try:
            # Get or create session
            session = self._session_service.get_or_create_session(session_id)
            
            log_info(
                "session_retrieved",
                session_id=session_id,
                history_length=len(session.history) if session.history else 0,
            )

            # Build conversation history in Gemini format
            history = []
            if session.history:
                for turn in session.history:
                    history.append(turn)

            # Add current user message
            history.append({"role": "user", "parts": [message]})

            # Generate response with conversation history
            response = self.agent.generate_content(
                history,
                config=types.GenerateContentConfig(
                    system_instruction=f"User ID: {user_id}. Session ID: {session_id}.",
                    temperature=0.7,
                ),
            )

            response_text = response.text

            # Add agent response to history
            history.append({"role": "model", "parts": [response_text]})

            # Save updated session (compaction is handled automatically by EventsCompactionConfig)
            session.history = history
            self._session_service.save_session(session)

            log_info(
                "chat_response_generated",
                user_id=user_id,
                response_length=len(response_text),
                session_id=session_id,
                history_length=len(history),
            )

            return response_text

        except Exception as e:
            log_error(
                "chat_error",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
                session_id=session_id,
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

    def get_session_history(self, session_id: str) -> list:
        """Get the conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of conversation turns with role and parts
        """
        session = self._session_service.get_session(session_id)
        return session.history if session and session.history else []

    def clear_session(self, session_id: str) -> None:
        """Clear the conversation history for a session.

        Args:
            session_id: Session identifier to clear
        """
        self._session_service.delete_session(session_id)
        log_info("session_cleared", session_id=session_id)

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs.

        Returns:
            List of session identifiers with conversation history
        """
        return self._session_service.list_sessions()


def create_orchestrator(
    profile_agent: Agent,
    recommender_agent: Agent,
    model_name: str = "gemini-2.5-flash-exp",
    database_url: Optional[str] = None,
    compaction_interval: int = 5,
    overlap_size: int = 2,
) -> ADKOrchestrator:
    """Factory function to create an ADK orchestrator.

    This is the recommended way to create an orchestrator instance.
    Agents must be created externally before passing to the orchestrator.

    Args:
        profile_agent: Pre-initialized Profile Agent (required)
        recommender_agent: Pre-initialized Recommender Agent (required)
        model_name: Gemini model to use for orchestrator (default: gemini-2.5-flash-exp)
        database_url: Optional database URL for session persistence
                     Examples:
                     - "sqlite:///sessions.db" (local SQLite)
                     - "sqlite:////tmp/sessions.db" (Cloud Run writable path)
                     - None (in-memory, not suitable for production)
        compaction_interval: Number of turns before triggering conversation compaction
                            (default: 5). Prevents unbounded history growth.
        overlap_size: Number of previous turns to keep during compaction
                     (default: 2). Maintains conversation context.

    Returns:
        Configured ADKOrchestrator instance

    Example:
        >>> from agents.profile_agent_adk import create_profile_agent
        >>> from agents.recommender_agent_adk import create_recommender_agent
        >>> from memory.storage import MemoryStorage
        >>> from rag.vector_store import VectorStore
        >>> from agents.event_ranker import create_event_ranker
        >>>
        >>> # Create dependencies
        >>> storage = MemoryStorage()
        >>> vector_store = VectorStore()
        >>> event_ranker = create_event_ranker()
        >>>
        >>> # Create agents
        >>> profile_agent = create_profile_agent(storage=storage)
        >>> recommender_agent = create_recommender_agent(
        ...     vector_store=vector_store,
        ...     event_ranker=event_ranker
        ... )
        >>>
        >>> # Create orchestrator with persistent sessions and compaction
        >>> orchestrator = create_orchestrator(
        ...     profile_agent=profile_agent,
        ...     recommender_agent=recommender_agent,
        ...     database_url="sqlite:///sessions.db",
        ...     compaction_interval=5,
        ...     overlap_size=2
        ... )
    """
    return ADKOrchestrator(
        profile_agent=profile_agent,
        recommender_agent=recommender_agent,
        model_name=model_name,
        database_url=database_url,
        compaction_interval=compaction_interval,
        overlap_size=overlap_size,
    )
