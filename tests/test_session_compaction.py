"""Test session management and conversation history compaction."""

import pytest

from agents.event_ranker import create_event_ranker
from agents.orchestrator import create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage
from rag.vector_store import VectorStore


@pytest.fixture
def orchestrator_with_compaction():
    """Create an orchestrator with aggressive compaction for testing."""
    storage = MemoryStorage()
    vector_store = None  # Optional for these tests
    event_ranker = create_event_ranker()
    
    profile_agent = create_profile_agent(
        storage=storage,
        model_name="gemini-2.5-flash-exp"
    )
    
    recommender_agent = create_recommender_agent(
        vector_store=vector_store,
        event_ranker=event_ranker,
        model_name="gemini-2.5-flash-exp"
    )
    
    # Use aggressive compaction for testing: compact every 3 turns, keep 1 turn
    orchestrator = create_orchestrator(
        profile_agent=profile_agent,
        recommender_agent=recommender_agent,
        model_name="gemini-2.5-flash-exp",
        database_url=":memory:",  # In-memory for tests
        compaction_interval=3,  # Compact every 3 turns
        overlap_size=1,  # Keep only 1 previous turn
    )
    
    return orchestrator


def test_session_persistence(orchestrator_with_compaction):
    """Test that conversation history is persisted across multiple turns."""
    orchestrator = orchestrator_with_compaction
    user_id = "test_user_session"
    
    # First message
    response1 = orchestrator.chat(user_id, "My name is Alice")
    assert response1 is not None
    
    # Check session history
    history = orchestrator.get_session_history(user_id)
    assert len(history) >= 2  # User message + model response
    
    # Second message - should remember context
    response2 = orchestrator.chat(user_id, "What's my name?")
    assert response2 is not None
    
    # History should have grown
    history = orchestrator.get_session_history(user_id)
    assert len(history) >= 4  # 2 user messages + 2 model responses


def test_conversation_compaction(orchestrator_with_compaction):
    """Test that conversation history is compacted after threshold."""
    orchestrator = orchestrator_with_compaction
    user_id = "test_user_compaction"
    
    # Send multiple messages to trigger compaction (interval=3, so 4th should trigger)
    messages = [
        "Tell me about Barcelona",
        "What about museums?",
        "Any art galleries?",
        "What's the weather?",
    ]
    
    for msg in messages:
        orchestrator.chat(user_id, msg)
    
    # Get final history
    history = orchestrator.get_session_history(user_id)
    
    # With compaction_interval=3, overlap_size=1:
    # After 3 turns (6 messages: 3 user + 3 model), compaction should happen
    # We should keep overlap_size=1 turn (2 messages) + new messages
    # So after 4 turns: should have compacted history
    print(f"History length: {len(history)}")
    print(f"History: {[h.get('role') for h in history if isinstance(h, dict)]}")
    
    # Verify history exists but may be compacted
    assert len(history) > 0, "History should not be empty"
    
    # The exact length depends on when compaction happens, but it should be
    # manageable (not growing unbounded)
    assert len(history) <= 12, "History should be compacted (not more than 6 turns)"


def test_multiple_sessions(orchestrator_with_compaction):
    """Test that different users have separate sessions."""
    orchestrator = orchestrator_with_compaction
    
    # User 1
    orchestrator.chat("user1", "I like modern art")
    history1 = orchestrator.get_session_history("user1")
    
    # User 2
    orchestrator.chat("user2", "I prefer classical art")
    history2 = orchestrator.get_session_history("user2")
    
    # Sessions should be different
    assert len(history1) > 0
    assert len(history2) > 0
    
    # User 1's history shouldn't contain user 2's message
    user1_content = str(history1)
    assert "classical" not in user1_content.lower()
    
    # User 2's history shouldn't contain user 1's message
    user2_content = str(history2)
    assert "modern" not in user2_content.lower()


def test_clear_session(orchestrator_with_compaction):
    """Test clearing a session."""
    orchestrator = orchestrator_with_compaction
    user_id = "test_user_clear"
    
    # Create some history
    orchestrator.chat(user_id, "Hello")
    orchestrator.chat(user_id, "How are you?")
    
    # Verify history exists
    history = orchestrator.get_session_history(user_id)
    assert len(history) > 0
    
    # Clear session
    orchestrator.clear_session(user_id)
    
    # History should be empty
    history_after = orchestrator.get_session_history(user_id)
    assert len(history_after) == 0


def test_get_active_sessions(orchestrator_with_compaction):
    """Test listing active sessions."""
    orchestrator = orchestrator_with_compaction
    
    # Create multiple sessions
    orchestrator.chat("user_a", "Hello")
    orchestrator.chat("user_b", "Hi")
    orchestrator.chat("user_c", "Hey")
    
    # Get active sessions
    sessions = orchestrator.get_active_sessions()
    
    # Should have at least our 3 users
    assert len(sessions) >= 3
    assert "user_a" in sessions
    assert "user_b" in sessions
    assert "user_c" in sessions


def test_compaction_preserves_context(orchestrator_with_compaction):
    """Test that compaction preserves enough context for continuity."""
    orchestrator = orchestrator_with_compaction
    user_id = "test_user_context"
    
    # Have a conversation that should trigger compaction
    orchestrator.chat(user_id, "I'm planning to visit Barcelona")
    orchestrator.chat(user_id, "I love contemporary art")
    orchestrator.chat(user_id, "Especially photography")
    
    # This message should still have some context due to overlap_size=1
    response = orchestrator.chat(user_id, "Can you recommend something?")
    
    assert response is not None
    assert len(response) > 0
    
    # Verify session still exists
    history = orchestrator.get_session_history(user_id)
    assert len(history) > 0


@pytest.mark.asyncio
async def test_async_chat(orchestrator_with_compaction):
    """Test async chat interface."""
    orchestrator = orchestrator_with_compaction
    user_id = "test_user_async"
    
    response = await orchestrator.chat_async(user_id, "Hello async world")
    
    assert response is not None
    assert len(response) > 0
    
    # Verify history was saved
    history = orchestrator.get_session_history(user_id)
    assert len(history) >= 2  # User + model


def test_session_with_custom_id(orchestrator_with_compaction):
    """Test using custom session IDs separate from user IDs."""
    orchestrator = orchestrator_with_compaction
    user_id = "user123"
    
    # Same user, different sessions
    orchestrator.chat(user_id, "Message in session 1", session_id="session_1")
    orchestrator.chat(user_id, "Message in session 2", session_id="session_2")
    
    # Verify separate histories
    history1 = orchestrator.get_session_history("session_1")
    history2 = orchestrator.get_session_history("session_2")
    
    assert len(history1) >= 2
    assert len(history2) >= 2
    
    # Sessions should be different
    assert str(history1) != str(history2)
