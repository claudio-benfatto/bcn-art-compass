import asyncio
from types import SimpleNamespace

from agents.orchestrator import ADKOrchestrator


class FakeRunner:
    """Minimal fake Runner that yields a single final event."""

    def __init__(self, text: str):
        self.app_name = "test-app"
        self.text = text

    async def run_async(self, user_id=None, session_id=None, new_message=None, run_config=None):
        yield SimpleNamespace(text=self.text)


class DummySessionService:
    """Simple in-memory session service for orchestrator history."""

    def __init__(self):
        self._store = {}

    def get_or_create_session(self, sid):
        if sid not in self._store:
            self._store[sid] = SimpleNamespace(session_id=sid, history=[])
        return self._store[sid]

    def get_session(self, sid):
        return self._store.get(sid)

    def save_session(self, sess):
        self._store[sess.session_id] = sess

    def delete_session(self, sid):
        self._store.pop(sid, None)

    def list_sessions(self):
        return list(self._store.keys())


def test_chat_async_uses_runner_via_chat_async():
    """chat_async should delegate to chat, which in turn uses the injected Runner."""
    runner = FakeRunner("Async run result")
    dummy_agent = SimpleNamespace(name="orchestrator")
    session_service = DummySessionService()
    orch = ADKOrchestrator(
        profile_agent=None,
        recommender_agent=None,
        agent=dummy_agent,
        session_service=session_service,
        runner=runner,
    )

    async def run_test():
        resp = await orch.chat_async(user_id="u1", message="Hello")
        assert resp == "Async run result"
        history = orch.get_session_history("u1")
        assert len(history) == 2  # user + model turns
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "model"

    asyncio.run(run_test())


def test_chat_async_propagates_errors_from_runner():
    """If the Runner raises, chat_async should surface the orchestrator error text."""

    class FailingRunner:
        def __init__(self):
            self.app_name = "test-app"

        async def run_async(self, user_id=None, session_id=None, new_message=None, run_config=None):
            raise RuntimeError("boom")

    dummy_agent = SimpleNamespace(name="orchestrator")
    session_service = DummySessionService()
    orch = ADKOrchestrator(
        profile_agent=None,
        recommender_agent=None,
        agent=dummy_agent,
        session_service=session_service,
        runner=FailingRunner(),
    )

    async def run_test():
        resp = await orch.chat_async(user_id="u2", message="Hi there")
        assert "internal error while running the multi-agent orchestrator" in resp
        history = orch.get_session_history("u2")
        # On error, we do not append the model turn
        assert len(history) == 0 or history[-1]["role"] != "model"

    asyncio.run(run_test())
