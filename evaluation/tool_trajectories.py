"""
Simple evaluation harness to inspect tool trajectories for key scenarios.

Scenarios:
1. Preference saving: user states likes/dislikes -> should trigger profile tools.
2. Recommendation with profile: user asks for events -> should trigger RAG + ranking.

This is intentionally lightweight and designed for manual inspection, inspired by
agent evaluation patterns (e.g. "tool trajectory" inspection).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, List, Optional

from google.genai import types as genai_types

from agents.orchestrator import ADKOrchestrator, create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage
from observability import configure_logging, log_info
from rag.models import SearchResult


@dataclass
class ToolStep:
    """Minimal representation of a single tool-related event in a trajectory."""

    event_type: Optional[str]
    agent: Optional[str] = None
    tool_name: Optional[str] = None
    status: Optional[str] = None
    payload_preview: Optional[str] = None


@dataclass
class Trajectory:
    """A sequence of tool-related steps for a single user message."""

    scenario: str
    user_id: str
    message: str
    steps: List[dict[str, Any]] = field(default_factory=list)
    final_response: Optional[str] = None


class DummyVectorStore:
    """Minimal stand-in for VectorStore to avoid heavy dependencies in evaluation.

    Returns a couple of static SearchResult objects so that recommend_events_tool
    has something to work with. This is not meant to be realistic, only to
    exercise the tool path and reasoning builder.
    """

    def query(self, query: str, k: int = 5, profile=None, filters=None):
        return [
            SearchResult(
                event_id="e1",
                title="Impressionist Landscapes",
                description="A collection of impressionist landscape paintings.",
                venue_name="Museu d'Art Modern",
                genres=["impressionism", "painting"],
                start_date=date(2025, 1, 10),
                end_date=date(2025, 3, 1),
                cost_range="€12",
                score=0.92,
                url="https://example.com/impressionist-landscapes",
                venue_latitude=41.3851,
                venue_longitude=2.1734,
            ),
            SearchResult(
                event_id="e2",
                title="Contemporary Sculpture Night",
                description="Evening of contemporary sculpture installations.",
                venue_name="MACBA",
                genres=["contemporary art", "sculpture"],
                start_date=date(2025, 1, 15),
                end_date=date(2025, 2, 28),
                cost_range="€10",
                score=0.88,
                url="https://example.com/contemporary-sculpture-night",
                venue_latitude=41.3830,
                venue_longitude=2.1667,
            ),
        ][:k]


class NoopEventRanker:
    """Trivial ranker used for evaluation so we can see raw RAG ordering."""

    def rank_events(self, results, profile, user_query: str = ""):
        return results


def _build_orchestrator_for_eval() -> ADKOrchestrator:
    """Create an orchestrator wired with in-memory storage and dummy RAG."""
    configure_logging("ERROR")  # keep evaluation output focused

    storage = MemoryStorage()

    # Profile agent uses Gemini; assumes GOOGLE_API_KEY is set in env.
    profile_agent = create_profile_agent(storage=storage)

    # Recommender agent with dummy vector store + noop ranker to avoid Chroma/torch.
    vector_store = DummyVectorStore()
    event_ranker = NoopEventRanker()
    recommender_agent = create_recommender_agent(
        vector_store=vector_store,
        event_ranker=event_ranker,
    )

    orchestrator = create_orchestrator(
        profile_agent=profile_agent,
        recommender_agent=recommender_agent,
        database_url=":memory:",
    )

    return orchestrator


async def _run_with_trajectory(
    orchestrator: ADKOrchestrator,
    user_id: str,
    message: str,
    scenario: str,
) -> Trajectory:
    """Run a single message through the orchestrator and capture tool trajectory."""
    traj = Trajectory(scenario=scenario, user_id=user_id, message=message)

    # Ensure an ADK runner session exists for this user/app combination,
    # mirroring the logic in ADKOrchestrator.chat so that Runner.run_async
    # doesn't fail with "Session not found" or app name mismatch issues.
    runner_svc = getattr(orchestrator, "_runner_session_service", None)
    runner = getattr(orchestrator, "_runner", None)
    if runner_svc is not None and runner is not None:
        adk_session = runner_svc.get_session_sync(  # type: ignore[attr-defined]
            app_name=runner.app_name,
            user_id=user_id,
            session_id=user_id,
        )
        if not adk_session:
            runner_svc.create_session_sync(  # type: ignore[attr-defined]
                app_name=runner.app_name,
                user_id=user_id,
                session_id=user_id,
            )

    # We bypass orchestrator.chat to access raw ADK events directly.
    async for event in orchestrator._runner.run_async(  # type: ignore[attr-defined]
        user_id=user_id,
        session_id=user_id,
        new_message=genai_types.UserContent(parts=[genai_types.Part(text=message)]),
        run_config=None,
    ):
        # Skip spurious string events (known ADK bug workaround).
        if isinstance(event, str):
            continue

        etype = getattr(event, "type", None)

        if etype in {"tool_call", "tool_result", "tool_error"}:
            step = {
                "event_type": etype,
                "agent": getattr(event, "agent", None) or getattr(event, "agent_name", None),
                "tool_name": getattr(event, "tool_name", None) or getattr(event, "name", None),
            }
            if etype == "tool_error":
                step["status"] = "error"
            elif etype == "tool_result":
                # capture a small preview of the payload
                payload = getattr(event, "output", None) or getattr(event, "response", None)
                step["payload_preview"] = (str(payload)[:200] + "...") if payload else None
            traj.steps.append(step)

        # Capture a rough final response when we see a text-bearing event
        raw_content = getattr(event, "content", None)
        if isinstance(raw_content, genai_types.Content):
            raw_content = "".join(
                (part.text or "")
                for part in getattr(raw_content, "parts", []) or []
                if getattr(part, "text", None)
            ) or None
        candidate = (
            getattr(event, "text", None)
            or raw_content
            or (" ".join(getattr(event, "parts", [])) if getattr(event, "parts", None) else None)
        )
        if candidate:
            traj.final_response = candidate

    return traj


async def run_preference_saving_scenario() -> Trajectory:
    """Scenario 1: user states preferences; we expect profile tools to be used."""
    orchestrator = _build_orchestrator_for_eval()
    user_id = "eval_user_prefs"
    message = "I love sculpture and contemporary art, but I don't like video art."
    log_info("eval_scenario_start", scenario="preference_saving", user_id=user_id)
    return await _run_with_trajectory(orchestrator, user_id, message, "preference_saving")


async def run_recommendation_with_profile_scenario() -> Trajectory:
    """Scenario 2: user asks for recommendations, expecting RAG + profile use."""
    orchestrator = _build_orchestrator_for_eval()
    user_id = "eval_user_recs"

    # Seed some preferences via a first message
    seed_message = "I really enjoy sculpture and contemporary art, and I live in Barcelona."
    await _run_with_trajectory(orchestrator, user_id, seed_message, "preference_seed")

    # Now ask for recommendations; this trajectory is what we care about.
    rec_message = "What art exhibitions would you recommend for this weekend?"
    log_info("eval_scenario_start", scenario="recommendation_with_profile", user_id=user_id)
    return await _run_with_trajectory(
        orchestrator,
        user_id,
        rec_message,
        "recommendation_with_profile",
    )


def main() -> None:
    """Run both scenarios and print trajectories as JSON for inspection."""
    async def _run_all():
        pref = await run_preference_saving_scenario()
        rec = await run_recommendation_with_profile_scenario()
        return [pref, rec]

    trajectories = asyncio.run(_run_all())
    for t in trajectories:
        print(json.dumps(asdict(t), ensure_ascii=False))


if __name__ == "__main__":
    main()


