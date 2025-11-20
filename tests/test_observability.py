"""
Unit tests for observability module.
"""

import pytest

from observability import (
    generate_correlation_id,
    get_correlation_id,
    log_agent_routing,
    log_info,
    log_memory_update,
    log_rag_query,
    log_tool_call,
    set_correlation_id,
)


@pytest.mark.unit
def test_generate_correlation_id():
    """Test that correlation IDs are generated and unique."""
    id1 = generate_correlation_id()
    id2 = generate_correlation_id()

    assert id1 is not None
    assert id2 is not None
    assert id1 != id2
    assert len(id1) > 0
    assert len(id2) > 0


@pytest.mark.unit
def test_set_and_get_correlation_id():
    """Test setting and getting correlation ID from context."""
    test_id = "test-correlation-id-123"

    # Set the correlation ID
    returned_id = set_correlation_id(test_id)
    assert returned_id == test_id

    # Get it back
    retrieved_id = get_correlation_id()
    assert retrieved_id == test_id


@pytest.mark.unit
def test_set_correlation_id_auto_generate():
    """Test that set_correlation_id auto-generates if not provided."""
    returned_id = set_correlation_id()

    assert returned_id is not None
    assert len(returned_id) > 0

    # Should be retrievable
    retrieved_id = get_correlation_id()
    assert retrieved_id == returned_id


@pytest.mark.unit
def test_log_info():
    """Test that log_info works without errors."""
    # This test just ensures the function doesn't crash
    # In a real scenario, you'd capture and verify log output
    log_info("test_event", key="value", number=42)


@pytest.mark.unit
def test_log_agent_routing():
    """Test agent routing log helper."""
    set_correlation_id("test-routing-123")
    log_agent_routing(
        agent_name="orchestrator",
        decision="route_to_rag",
        user_query="find art exhibitions",
    )


@pytest.mark.unit
def test_log_rag_query():
    """Test RAG query log helper."""
    set_correlation_id("test-rag-123")
    log_rag_query(
        query="contemporary sculpture",
        num_results=5,
        filters={"tags": ["sculpture"]},
    )


@pytest.mark.unit
def test_log_memory_update():
    """Test memory update log helper."""
    set_correlation_id("test-memory-123")
    log_memory_update(
        user_id="user_001",
        operation="save",
        changes={"favorite_genres": ["sculpture", "contemporary art"]},
    )


@pytest.mark.unit
def test_log_tool_call():
    """Test tool call log helper."""
    set_correlation_id("test-tool-123")
    log_tool_call(
        tool_name="event_search",
        parameters={"query": "art exhibitions", "limit": 10},
        result_status="success",
    )
