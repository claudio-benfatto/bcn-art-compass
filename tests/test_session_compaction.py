"""Test session management and conversation history compaction."""

import asyncio
from types import SimpleNamespace

import pytest

from agents.orchestrator import ADKOrchestrator


class FakeRunner:
    """Minimal fake Runner used to test session history/compaction without real ADK calls."""

    def __init__(self, text: str = "dummy response"):
        self.app_name = "test-app"
        self.text = text
        # Provide an agent-like object so orchestrator.agent.name works
        self.agent = SimpleNamespace(name="orchestrator")

    async def run_async(self, user_id=None, session_id=None, new_message=None, run_config=None):
        # Single final event with the configured text
        yield SimpleNamespace(text=self.text)


class DummySessionService:
    def __init__(self):
        self._store = {}

    def get_or_create_session(self, sid):
        if sid not in self._store:
            self._store[sid] = type("Sess", (), {"session_id": sid, "history": []})()
        return self._store[sid]

    def save_session(self, sess):
        self._store[sess.session_id] = sess

    def get_session(self, sid):
        return self._store.get(sid)

    def list_sessions(self):
        return list(self._store.keys())

    def delete_session(self, sid):
        if sid in self._store:
            del self._store[sid]


def make_orchestrator():
    runner = FakeRunner("dummy response")
    return ADKOrchestrator(
        profile_agent=None,
        recommender_agent=None,
        agent=runner.agent,
        session_service=DummySessionService(),
        compaction_interval=3,
        overlap_size=1,
        runner=runner,
    )


def test_session_persistence_injected():
    orchestrator = make_orchestrator()
    user_id = "test_injected_user"
    response1 = orchestrator.chat(user_id, "Hello!")
    assert response1 == "dummy response"
    history = orchestrator.get_session_history(user_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "model"


def test_conversation_compaction():
    orchestrator = make_orchestrator()
    user_id = "test_user_compaction"
    messages = [
        "Tell me about Barcelona",
        "What about museums?",
        "Any art galleries?",
        "What's the weather?",
    ]
    for msg in messages:
        orchestrator.chat(user_id, msg)
    history = orchestrator.get_session_history(user_id)
    assert len(history) == 8  # 4 user + 4 model


def test_multiple_sessions():
    orchestrator = make_orchestrator()
    orchestrator.chat("user1", "I like modern art")
    history1 = orchestrator.get_session_history("user1")
    orchestrator.chat("user2", "I prefer classical art")
    history2 = orchestrator.get_session_history("user2")
    assert len(history1) == 2
    assert len(history2) == 2
    user1_content = str(history1)
    assert "classical" not in user1_content.lower()
    user2_content = str(history2)
    assert "modern" not in user2_content.lower()


def test_clear_session():
    orchestrator = make_orchestrator()
    user_id = "test_user_clear"
    orchestrator.chat(user_id, "Hello")
    orchestrator.chat(user_id, "How are you?")
    history = orchestrator.get_session_history(user_id)
    assert len(history) == 4
    orchestrator.clear_session(user_id)
    history_after = orchestrator.get_session_history(user_id)
    assert len(history_after) == 0


def test_get_active_sessions():
    orchestrator = make_orchestrator()
    orchestrator.chat("user_a", "Hello")
    orchestrator.chat("user_b", "Hi")
    orchestrator.chat("user_c", "Hey")
    sessions = orchestrator.get_active_sessions()
    assert "user_a" in sessions
    assert "user_b" in sessions
    assert "user_c" in sessions


def test_compaction_preserves_context():
    orchestrator = make_orchestrator()
    user_id = "test_user_context"
    orchestrator.chat(user_id, "I'm planning to visit Barcelona")
    orchestrator.chat(user_id, "I love contemporary art")
    orchestrator.chat(user_id, "Especially photography")
    response = orchestrator.chat(user_id, "Can you recommend something?")
    assert response == "dummy response"
    history = orchestrator.get_session_history(user_id)
    assert len(history) == 8


@pytest.mark.asyncio
async def test_async_chat():
    orchestrator = make_orchestrator()
    user_id = "test_user_async"
    response = await orchestrator.chat_async(user_id, "Hello async world")
    assert response == "dummy response"
    history = orchestrator.get_session_history(user_id)
    assert len(history) == 2


def test_session_with_custom_id():
    orchestrator = make_orchestrator()
    user_id = "user123"
    orchestrator.chat(user_id, "Message in session 1", session_id="session_1")
    orchestrator.chat(user_id, "Message in session 2", session_id="session_2")
    history1 = orchestrator.get_session_history("session_1")
    history2 = orchestrator.get_session_history("session_2")
    import asyncio
    import pytest
    from agents.orchestrator import ADKOrchestrator
    assert len(history2) == 2
    assert str(history1) != str(history2)
