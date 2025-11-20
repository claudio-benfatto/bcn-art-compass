"""
MCP event_search tool.

Provides a tool interface for searching events using the RAG vector store.
"""

from typing import Optional

from observability import log_tool_call
from rag.models import SearchResult
from rag.vector_store import VectorStore


def event_search(
    query: str,
    limit: int = 5,
    filters: Optional[dict] = None,
    vector_store: Optional[VectorStore] = None,
) -> list[SearchResult]:
    """
    Search for cultural events using semantic search.

    This is an MCP-style tool that wraps the RAG vector store query.

    Args:
        query: Natural language search query
        limit: Maximum number of results to return
        filters: Optional metadata filters (e.g., {"genres": "sculpture"})
        vector_store: VectorStore instance. If None, creates a new one

    Returns:
        List of SearchResult objects
    """
    log_tool_call(
        tool_name="event_search",
        parameters={"query": query, "limit": limit, "filters": filters or {}},
    )

    # Initialize vector store if not provided
    if vector_store is None:
        vector_store = VectorStore()

    # Query the vector store
    results = vector_store.query(query_text=query, k=limit, filters=filters)

    log_tool_call(
        tool_name="event_search",
        parameters={"query": query, "limit": limit},
        result_status="success",
    )

    return results


# Tool metadata for MCP registration (future use)
TOOL_METADATA = {
    "name": "event_search",
    "description": "Search for cultural events in Barcelona using natural language queries",
    "parameters": {
        "query": {"type": "string", "description": "Natural language search query"},
        "limit": {"type": "integer", "description": "Maximum number of results", "default": 5},
        "filters": {
            "type": "object",
            "description": "Optional metadata filters for refining search",
            "optional": True,
        },
    },
    "returns": {
        "type": "array",
        "description": "List of matching events with venue information",
    },
}
