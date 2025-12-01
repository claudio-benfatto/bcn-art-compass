import pytest
from types import SimpleNamespace

from agents.orchestrator import ADKOrchestrator


class FakeRunner:
    """Minimal fake Runner used to test injected session persistence."""

    def __init__(self, text: str):
        self.app_name = "test-app"
        self.text = text
        # Provide an agent-like object so orchestrator.agent.name works
        self.agent = SimpleNamespace(name="orchestrator")

    async def run_async(self, user_id=None, session_id=None, new_message=None, run_config=None):
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


@pytest.fixture
def orchestrator_injected():
    runner = FakeRunner("dummy response")
    session_service = DummySessionService()
    return ADKOrchestrator(
        profile_agent=None,
        recommender_agent=None,
        agent=runner.agent,
        session_service=session_service,
        runner=runner,
    )

def test_injected_session_persistence(orchestrator_injected):
    user_id = "test_injected_user"
    response1 = orchestrator_injected.chat(user_id, "Hello!")
    assert response1 == "dummy response"
    history = orchestrator_injected.get_session_history(user_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "model"
