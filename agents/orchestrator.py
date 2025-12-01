"""ADK-based Orchestrator Agent for BCN Art Compass.

This module provides the main orchestrator agent that coordinates all user interactions.
It uses Google's Agent Development Kit (ADK) with a multi-agent architecture:

- Orchestrator Agent: Routes queries and coordinates between specialized agents
- Profile Agent: Manages user preferences and profile data (separate LLM)
- Recommender Agent: Searches and recommends events (separate LLM)

Each agent is a separate Gemini model instance that can be called via AgentTool.
"""

from typing import Optional
import contextlib
import io
import json
import re
import sys
import time

from google.adk import Agent, Runner
from google.adk.apps.app import EventsCompactionConfig
from agents.adk_workaround import patch_event_compaction
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from google.adk.tools import AgentTool
from google.genai import types

from agents.prompts import ORCHESTRATOR_INSTRUCTIONS
from observability import log_error, log_info

def summarize_profile_update(payload: dict) -> str:
    """Create deterministic confirmation text from profile diff payload.

    Expected payload keys: profile, updated. The updated dict may include:
    favorite_genres_added, favorite_genres_removed, favorite_genres_not_found,
    disliked_genres_added, disliked_genres_removed, disliked_genres_not_found,
    favorite_artists_added, favorite_artists_removed, favorite_artists_not_found,
    location_changed.
    If no changes: returns 'No profile changes applied.'
    """
    try:
        upd = payload.get("updated", {}) or {}
        prof = payload.get("profile", {}) or {}
    except AttributeError:
        return "No profile changes applied."

    parts: list[str] = []

    def add_segment(label: str, values: list[str], action: str) -> None:
        if values:
            joined = ", ".join(values)
            parts.append(f"{action} {joined} {label}")

    add_segment("to favorite genres", upd.get("favorite_genres_added", []), "Added")
    add_segment("from favorite genres", upd.get("favorite_genres_removed", []), "Removed")
    if upd.get("favorite_genres_not_found"):
        parts.append(
            f"Not found in favorite genres: {', '.join(upd['favorite_genres_not_found'])}"
        )

    add_segment("to disliked genres", upd.get("disliked_genres_added", []), "Added")
    add_segment("from disliked genres", upd.get("disliked_genres_removed", []), "Removed")
    if upd.get("disliked_genres_not_found"):
        parts.append(
            f"Not found in disliked genres: {', '.join(upd['disliked_genres_not_found'])}"
        )

    add_segment("to favorite artists", upd.get("favorite_artists_added", []), "Added")
    add_segment("from favorite artists", upd.get("favorite_artists_removed", []), "Removed")
    if upd.get("favorite_artists_not_found"):
        parts.append(
            f"Not found in favorite artists: {', '.join(upd['favorite_artists_not_found'])}"
        )

    if upd.get("location_changed") and prof.get("location"):
        parts.append(f"Location set to {prof['location']}")

    if not parts:
        return "No profile changes applied."

    return ". ".join(parts) + "."


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
        profile_agent: Optional[object],
        recommender_agent: Optional[object],
        model_name: str = "gemini-2.5-pro",
        database_url: Optional[str] = None,
        compaction_interval: int = 5,
        overlap_size: int = 2,
        agent: Optional[object] = None,
        session_service: Optional[object] = None,
        runner: Optional[object] = None,
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
            profile_agent_name=getattr(profile_agent, "name", None),
            recommender_agent_name=getattr(recommender_agent, "name", None),
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

        # Allow direct injection of session_service for tests
        if session_service is not None:
            self._session_service = session_service
        elif not database_url or database_url in {":memory:", "memory"} or database_url.startswith("sqlite"):
            # Always use in-memory session storage for local/dev
            class _InMemSess:
                def __init__(self):
                    self._store: dict[str, "_SessObj"] = {}

                def get_or_create_session(self, sid: str):
                    if sid not in self._store:
                        self._store[sid] = _SessObj(session_id=sid)
                    return self._store[sid]

                def get_session(self, sid: str):
                    return self._store.get(sid)

                def save_session(self, sess):  # noqa: D401
                    self._store[sess.session_id] = sess

                def delete_session(self, sid: str):
                    self._store.pop(sid, None)

                def list_sessions(self):
                    return list(self._store.keys())

            class _SessObj:
                def __init__(self, session_id: str):
                    self.session_id = session_id
                    self.history: list[dict] | None = []

            self._session_service = _InMemSess()
            log_info(
                "session_service_initialized",
                database_url="in-memory-fallback",
                compaction_enabled=False,
                compaction_interval=compaction_interval,
                overlap_size=overlap_size,
            )
        elif database_url and (database_url.startswith("firestore") or database_url.startswith("gs://")):
            # Use Firestore/Cloud Storage with events compaction for Google Cloud
            self._session_service = DatabaseSessionService(
                db_url=database_url,
                events_compaction_config=compaction_config,
            )
            log_info(
                "session_service_initialized",
                database_url=database_url,
                compaction_enabled=True,
                compaction_interval=compaction_interval,
                overlap_size=overlap_size,
            )
        else:
            # Fallback: always use in-memory for any other local config
            class _InMemSess:
                def __init__(self):
                    self._store: dict[str, "_SessObj"] = {}

                def get_or_create_session(self, sid: str):
                    if sid not in self._store:
                        self._store[sid] = _SessObj(session_id=sid)
                    return self._store[sid]

                def get_session(self, sid: str):
                    return self._store.get(sid)

                def save_session(self, sess):  # noqa: D401
                    self._store[sess.session_id] = sess

                def delete_session(self, sid: str):
                    self._store.pop(sid, None)

                def list_sessions(self):
                    return list(self._store.keys())

            class _SessObj:
                def __init__(self, session_id: str):
                    self.session_id = session_id
                    self.history: list[dict] | None = []

            self._session_service = _InMemSess()
            log_info(
                "session_service_initialized",
                database_url="in-memory-fallback",
                compaction_enabled=False,
                compaction_interval=compaction_interval,
                overlap_size=overlap_size,
            )

        # Allow direct injection of agent/runner for tests
        if runner is not None:
            # Testing/custom mode: use provided agent/runner and skip ADK wiring.
            self.agent = agent or getattr(runner, "agent", None) or object()
            self._runner = runner
            self._runner_session_service = None
        else:
            # Normal ADK Agent wiring
            if agent is not None:
                self.agent = agent
            else:
                self.agent = Agent(
                    model=model_name,
                    name="orchestrator",
                    instruction=ORCHESTRATOR_INSTRUCTIONS,
                    tools=[
                        AgentTool(agent=profile_agent),
                        AgentTool(agent=recommender_agent),
                    ],
                )

            # ADK Runner for full multi-agent + tools execution (RAG, profile, etc.)
            # Uses a separate in-memory session service from the orchestrator's own
            # simple history store.
            self._runner_session_service = InMemorySessionService()
            self._runner = Runner(
                app_name="bcn-art-compass-orchestrator",
                agent=self.agent,
                session_service=self._runner_session_service,
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

        start_ts = time.time()

        try:
            # Get or create simple history session (for our own storage/compaction)
            session = self._session_service.get_or_create_session(session_id)

            log_info(
                "session_retrieved",
                session_id=session_id,
                history_length=len(session.history) if session.history else 0,
            )

            # Ensure ADK Runner session exists (separate from our simple history),
            # but only when we are using a real ADK InMemorySessionService.
            if self._runner_session_service is not None:
                adk_svc = self._runner_session_service
                adk_session = adk_svc.get_session_sync(
                    app_name=self._runner.app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if not adk_session:
                    adk_session = adk_svc.create_session_sync(
                        app_name=self._runner.app_name,
                        user_id=user_id,
                        session_id=session_id,
                    )

            # Run full ADK agent graph (orchestrator + profile + recommender + tools)
            import asyncio

            async def _run():
                final: Optional[str] = None
                confirmation_text: Optional[str] = None

                log_info(
                    "runner_starting",
                    session_id=session_id,
                    user_id=user_id,
                )

                first_event = True
                async for event in self._runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.UserContent(
                        parts=[types.Part(text=message)]
                    ),
                    run_config=None,
                ):
                    if first_event:
                        log_info("runner_first_event_received")
                        first_event = False
                    
                    if isinstance(event, str):
                        log_info("adk_bug_skipped_string_event", event_value=repr(event))
                        continue

                    etype = getattr(event, "type", None)
                    compaction = patch_event_compaction(event)

                    # Tool events (profile updates, RAG calls, etc.)
                    if etype in {"tool_call", "tool_result", "tool_error"}:
                        tool_name = getattr(event, "tool_name", None) or getattr(
                            event, "name", "unknown_tool"
                        )
                        status = "error" if etype == "tool_error" else "ok"
                        if not session.history:
                            session.history = []
                        raw_payload = None
                        if etype == "tool_result":
                            for attr in ("output", "response", "result", "data"):
                                raw_payload = getattr(event, attr, None)
                                if raw_payload:
                                    break
                            if isinstance(raw_payload, dict) and {
                                "profile",
                                "updated",
                            }.issubset(raw_payload.keys()):
                                confirmation_text = summarize_profile_update(
                                    raw_payload
                                )
                                log_info(
                                    "profile_update_confirmed",
                                    user_id=user_id,
                                    confirmation=confirmation_text,
                                    favorite_genres_added=len(
                                        raw_payload["updated"].get(
                                            "favorite_genres_added", []
                                        )
                                    ),
                                    favorite_genres_removed=len(
                                        raw_payload["updated"].get(
                                            "favorite_genres_removed", []
                                        )
                                    ),
                                )
                                # raw_payload may contain date/datetime objects; make it JSON-safe
                                try:
                                    payload_str = json.dumps(raw_payload, default=str)
                                except TypeError:
                                    payload_str = repr(raw_payload)
                                session.history.append(
                                    {
                                        "role": "tool",
                                        "content": payload_str,
                                    }
                                )
                                continue
                        session.history.append(
                            {"role": "tool", "content": f"{tool_name}:{status}"}
                        )
                        continue

                    # Model text candidates
                    raw_content = getattr(event, "content", None)
                    # If content is a google.genai.types.Content object, extract text parts
                    if isinstance(raw_content, types.Content):
                        raw_content = "".join(
                            (part.text or "")
                            for part in getattr(raw_content, "parts", []) or []
                            if getattr(part, "text", None)
                        ) or None

                    candidate = (
                        getattr(event, "text", None)
                        or raw_content
                        or (
                            " ".join(getattr(event, "parts", []))
                            if getattr(event, "parts", None)
                            else None
                        )
                    )
                    # ADK event types may vary; treat any non-empty candidate as a
                    # potential final answer, preferring confirmation_text when set.
                    if candidate:
                        if (
                            confirmation_text
                            and not message.strip().lower().startswith("show")
                            and not message.strip().lower().startswith("recommend")
                        ):
                            final = confirmation_text
                        else:
                            final = (
                                f"{confirmation_text} {candidate}"
                                if confirmation_text
                                else candidate
                            )

                return final or "(no response)"

            # Retry wrapper to handle 429 RESOURCE_EXHAUSTED from Gemini.
            # We also filter noisy deprecation prints from underlying SDKs while
            # preserving all other stdout/stderr output. We track timing for the
            # runner portion to help diagnose slow chats.
            max_retries = 10
            attempt = 0
            last_error: Optional[Exception] = None
            runner_ms = 0
            runner_attempts = 0
            while True:
                try:
                    stdout_buf = io.StringIO()
                    stderr_buf = io.StringIO()
                    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                        t0 = time.time()
                        response_text = asyncio.run(_run())
                        runner_ms += int((time.time() - t0) * 1000)
                        runner_attempts += 1

                    # Re-emit any captured stdout/stderr except known noisy deprecation lines
                    def _reemit_filtered(buf: io.StringIO, stream) -> None:
                        text = buf.getvalue()
                        if not text:
                            return
                        for line in text.splitlines():
                            if line.strip() == "Deprecated. Please migrate to the async method.":
                                continue
                            print(line, file=stream)

                    _reemit_filtered(stdout_buf, sys.stdout)
                    _reemit_filtered(stderr_buf, sys.stderr)

                    break
                except Exception as run_err:
                    msg = str(run_err)
                    last_error = run_err
                    # Detect quota / rate limit errors
                    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                        if attempt >= max_retries:
                            log_error(
                                "chat_run_async_quota_retries_exhausted",
                                user_id=user_id,
                                session_id=session_id,
                                error=msg,
                                attempts=attempt + 1,
                            )
                            raise
                        # Try to extract suggested retry delay (e.g. retryDelay: '40s')
                        delay_seconds = 5.0
                        m = re.search(r"retryDelay['\"]?:\\s*'(?P<secs>\\d+)s'", msg)
                        if m:
                            try:
                                delay_seconds = float(m.group("secs"))
                            except ValueError:
                                delay_seconds = 5.0
                        log_info(
                            "chat_run_async_quota_retry",
                            user_id=user_id,
                            session_id=session_id,
                            delay_seconds=delay_seconds,
                            attempt=attempt + 1,
                        )
                        time.sleep(delay_seconds)
                        attempt += 1
                        continue
                    # Non-quota error: re-raise to outer handler
                    raise

            # Append model response to history in simplified event format
            if not session.history:
                session.history = []
            session.history.append({"role": "user", "content": message})
            session.history.append({"role": "model", "content": response_text})

            # Persist updated session
            self._session_service.save_session(session)

            total_ms = int((time.time() - start_ts) * 1000)
            log_info(
                "chat_timing",
                user_id=user_id,
                session_id=session_id,
                total_ms=total_ms,
                runner_ms=runner_ms,
                runner_attempts=runner_attempts or 0,
            )

            log_info(
                "chat_response_generated",
                user_id=user_id,
                response_length=len(response_text),
                session_id=session_id,
                history_length=len(session.history),
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
            # No silent fallback – surface a clear orchestrator error
            return (
                "I encountered an internal error while running the multi-agent orchestrator. "
                "Please check the server logs for details."
            )

    # --- Internal helpers (MVP scope) -------------------------------------------------
    def _build_messages(self, session, new_user_message: str) -> list[dict]:
        """Build messages list (role/content) from session history + new user message.

        History stored as simplified events: {role, content}.
        Returns list of dicts suitable for passing to run_async.
        """
        messages: list[dict] = []
        if session and session.history:
            for turn in session.history:
                role = turn.get("role")
                text = turn.get("content") or (turn.get("parts") or [""])[0]
                if role and text is not None:
                    messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": new_user_message})
        return messages

    def _sync_fallback(self, user_id: str, message: str, session_id: str) -> str:
        """Dedicated fallback path invoking existing sync chat implementation."""
        return self.chat(user_id=user_id, message=message, session_id=session_id)

    async def chat_async(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Async wrapper around sync chat to avoid ADK run_async incompatibilities."""
        import asyncio

        session_id = session_id or user_id

        log_info(
            "processing_user_message_async",
            user_id=user_id,
            message=message[:100],
            session_id=session_id,
        )

        try:
            return await asyncio.to_thread(self.chat, user_id, message, session_id)
        except Exception as e:
            log_error(
                "chat_async_error",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
                session_id=session_id,
            )
            return (
                "I apologize, but I encountered an error while processing your request. "
                "Please try again or rephrase your question."
            )

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

    # --- Streaming interface ---------------------------------------------------------
    async def stream_events(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ):
        """Async generator yielding structured event frames for WebSocket/SSE.

        Frame schema (dict):
        {
          'type': 'token'|'tool'|'final'|'error'|'info',
          'content': str | None,
          'tool': optional tool name,
          'status': optional status ('ok'|'error'|'started'),
          'seq': incremental integer
        }

        Notes:
        - Falls back to single final frame if run_async unavailable.
        - Tool events mapped to lightweight traces.
        - Tokens: if the ADK event exposes partial text via 'text' and type not final, emit as 'token'.
        - History persistence occurs after final frame emission.
        """
        session_id = session_id or user_id
        seq = 0
        try:
            # For now, reuse the synchronous chat path and expose a single final
            # frame to streaming clients. This avoids depending on ADK's
            # Agent.run_async API, which has changed across versions.
            final_text = self.chat(user_id=user_id, message=message, session_id=session_id)
            yield {
                "type": "final",
                "content": final_text,
                "seq": seq,
            }
        except Exception as e:
            yield {
                "type": "error",
                "content": f"Streaming error: {e}",
                "seq": seq,
            }


def create_orchestrator(
    profile_agent: Agent,
    recommender_agent: Agent,
    model_name: str = "gemini-2.5-flash",
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
        model_name: Gemini model to use for orchestrator (default: gemini-1.5-flash)
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
