from fastapi.testclient import TestClient

from api.main import app, orchestrator

client = TestClient(app)


def test_ws_stream_final_only_fallback(monkeypatch):
    # Ensure orchestrator exists
    assert orchestrator is not None

    # Remove run_async to trigger fallback path returning final only
    if hasattr(orchestrator.agent, "run_async"):
        delattr(orchestrator.agent, "run_async")

    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"user_id": "u1", "message": "Hello"})
        frame = ws.receive_json()
        assert frame["type"] == "final"
        assert "content" in frame and frame["content"]


def test_ws_stream_with_mock_events(monkeypatch):
    # Re-add mock run_async to orchestrator.agent
    async def fake_run_async(messages=None, user_id=None):
        # Simulate token chunks and a tool call sequence
        yield type("E", (), {"type": "tool_call", "tool_name": "event_search"})()
        yield type("E", (), {"type": "tool_result", "tool_name": "event_search"})()
        yield type("E", (), {"type": "response", "text": "First part"})()
        yield type("E", (), {"type": "ai_response", "text": "Second part"})()
        yield type("E", (), {"type": "final", "text": "Final answer"})()

    orchestrator.agent.run_async = fake_run_async  # type: ignore[attr-defined]

    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"user_id": "u2", "message": "Stream please"})
        frames = []
        while True:
            data = ws.receive_json()
            frames.append(data)
            if data.get("type") == "final":
                break
        types_sequence = [f["type"] for f in frames]
        assert types_sequence[0] == "tool"
        assert types_sequence[1] == "tool"
        assert "token" in types_sequence or "final" in types_sequence
        assert frames[-1]["type"] == "final"
        assert frames[-1]["content"] == "Final answer"
