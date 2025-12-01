"""
Observability module with structured logging.

Provides a lightweight observability layer for tracking agent decisions,
RAG queries, memory updates, and MCP tool calls with correlation IDs.
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Any, Optional, Union

import structlog

# Context variable to store correlation ID for the current session/request
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def configure_logging(log_level: Union[str, int] = "INFO") -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Normalize log_level to an integer understood by the standard logging module.
    if isinstance(log_level, str):
        level_name = log_level.upper()
        level = getattr(logging, level_name, logging.INFO)
    else:
        level = int(log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID for tracking a user session.

    Returns:
        A unique correlation ID string
    """
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set the correlation ID for the current context.
    If no ID is provided, generates a new one.

    Args:
        correlation_id: Optional correlation ID to use

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = generate_correlation_id()

    correlation_id_ctx.set(correlation_id)
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.

    Returns:
        The current correlation ID or None if not set
    """
    return correlation_id_ctx.get()


def log_event(
    event: str,
    level: str = "info",
    **kwargs: Any,
) -> None:
    """
    Log an event with structured logging and correlation ID.

    Args:
        event: The event name/description
        level: Log level (debug, info, warning, error, critical)
        **kwargs: Additional context to include in the log
    """
    logger = structlog.get_logger()
    log_func = getattr(logger, level.lower())

    # Ensure correlation_id is in the log
    if "correlation_id" not in kwargs:
        correlation_id = get_correlation_id()
        if correlation_id:
            kwargs["correlation_id"] = correlation_id

    log_func(event, **kwargs)


# Convenience functions for common log levels
def log_debug(event: str, **kwargs: Any) -> None:
    """Log a debug event."""
    log_event(event, level="debug", **kwargs)


def log_info(event: str, **kwargs: Any) -> None:
    """Log an info event."""
    log_event(event, level="info", **kwargs)


def log_warning(event: str, **kwargs: Any) -> None:
    """Log a warning event."""
    log_event(event, level="warning", **kwargs)


def log_error(event: str, **kwargs: Any) -> None:
    """Log an error event."""
    log_event(event, level="error", **kwargs)


def log_critical(event: str, **kwargs: Any) -> None:
    """Log a critical event."""
    log_event(event, level="critical", **kwargs)


# Agent-specific logging helpers
def log_agent_routing(
    agent_name: str,
    decision: str,
    **kwargs: Any,
) -> None:
    """
    Log an agent routing decision.

    Args:
        agent_name: Name of the agent making the decision
        decision: The routing decision made
        **kwargs: Additional context
    """
    log_info(
        "agent_routing",
        agent=agent_name,
        decision=decision,
        **kwargs,
    )


def log_rag_query(
    query: str,
    num_results: int,
    filters: Optional[dict] = None,
    **kwargs: Any,
) -> None:
    """
    Log a RAG query operation.

    Args:
        query: The search query
        num_results: Number of results requested
        filters: Optional filters applied
        **kwargs: Additional context
    """
    log_info(
        "rag_query",
        query=query,
        num_results=num_results,
        filters=filters or {},
        **kwargs,
    )


def log_memory_update(
    user_id: str,
    operation: str,
    changes: dict,
    **kwargs: Any,
) -> None:
    """
    Log a memory update operation.

    Args:
        user_id: ID of the user whose memory is being updated
        operation: Type of operation (load, save, update)
        changes: Dictionary describing what changed
        **kwargs: Additional context
    """
    log_info(
        "memory_update",
        user_id=user_id,
        operation=operation,
        changes=changes,
        **kwargs,
    )


def log_tool_call(
    tool_name: str,
    parameters: dict,
    result_status: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """
    Log an MCP tool call.

    Args:
        tool_name: Name of the tool being called
        parameters: Parameters passed to the tool
        result_status: Optional status of the tool execution (success, error)
        **kwargs: Additional context
    """
    log_info(
        "tool_call",
        tool=tool_name,
        parameters=parameters,
        result_status=result_status,
        **kwargs,
    )


# Initialize logging configuration on module import
configure_logging()
