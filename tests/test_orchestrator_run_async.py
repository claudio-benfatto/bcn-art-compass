import asyncio
from types import SimpleNamespace

from agents.orchestrator import ADKOrchestrator


class DummyModel:
    def generate_content(self, contents, config=None, **kwargs):
        class R:
            def __init__(self):
                self.text = "Fallback sync response"
        return R()


async def fake_run_async(messages=None, user_id=None, session_id=None, context=None, tool_results=None, event=None, **kwargs):
    # Simulate a streamed sequence ending with a final response event.
    yield SimpleNamespace(type="final", text="Async run result")



class StubAgent:
    def __init__(self, name, with_run_async=True):
        self.name = name
        self.description = f"Stub agent for {name}"
        self.model = DummyModel()
        self._with_run_async = with_run_async

    # Only define run_async if with_run_async is True
    # This allows orchestrator to fall back to sync path when not present
    def __init__(self, name, with_run_async=True):
        self.name = name
        self.description = f"Stub agent for {name}"
        self.model = DummyModel()
        if with_run_async:
            async def run_async(user_id=None, message=None, **kwargs):
                from types import SimpleNamespace
                yield SimpleNamespace(type="final", text="Async run result")
            self.run_async = run_async

def make_stub_agent(name: str, with_run_async=True):
    return StubAgent(name, with_run_async)


def test_chat_async_uses_run_async(monkeypatch):
    profile_agent = make_stub_agent("profile_agent", with_run_async=True)
    recommender_agent = make_stub_agent("recommender_agent", with_run_async=True)

    orch = ADKOrchestrator(profile_agent=profile_agent, recommender_agent=recommender_agent)

    async def run_test():
        resp = await orch.chat_async(user_id="u1", message="Hello")
        assert resp == "Async run result"
        history = orch.get_session_history("u1")
        assert len(history) == 2  # user + model turns
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "model"

    asyncio.run(run_test())


def test_chat_async_fallback_to_sync(monkeypatch):
    profile_agent = make_stub_agent("profile_agent", with_run_async=False)
    recommender_agent = make_stub_agent("recommender_agent", with_run_async=False)

    orch = ADKOrchestrator(profile_agent=profile_agent, recommender_agent=recommender_agent)

    async def run_test():
        resp = await orch.chat_async(user_id="u2", message="Hi there")
        assert resp == "Fallback sync response"
        history = orch.get_session_history("u2")
        assert len(history) == 2
        assert history[1]["content"] == "Fallback sync response"

    asyncio.run(run_test())
