import pytest
from agents.orchestrator import ADKOrchestrator

class DummyAgent:
    def __init__(self):
        self.name = "dummy"
        self.description = "dummy agent"
        self.model = self
    def generate_content(self, messages, config=None):
        class R:
            text = "dummy response"
        return R()

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
    agent = DummyAgent()
    session_service = DummySessionService()
    return ADKOrchestrator(
        profile_agent=None,
        recommender_agent=None,
        agent=agent,
        session_service=session_service,
    )

def test_injected_session_persistence(orchestrator_injected):
    user_id = "test_injected_user"
    response1 = orchestrator_injected.chat(user_id, "Hello!")
    assert response1 == "dummy response"
    history = orchestrator_injected.get_session_history(user_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "model"
