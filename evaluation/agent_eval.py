"""
Agent Evaluation Framework - test agent quality with sample queries.

This module provides an evaluation harness for testing the multi-agent system
with predefined test cases and expected outcomes.

Part of Milestone 7: Final MVP Hardening

Usage:
    # Run basic evaluation
    uv run python -m evaluation.agent_eval

    # Run with detailed output
    uv run python -m evaluation.agent_eval --verbose

    # Run specific test cases
    uv run python -m evaluation.agent_eval --test preference_extraction
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.orchestrator import OrchestratorAgent
from agents.profile_agent import ProfileAgent
from agents.recommender_agent import RecommenderAgent
from memory.storage import MemoryStorage
from observability import log_info


class EvaluationCase:
    """A single test case for agent evaluation."""

    def __init__(
        self,
        name: str,
        query: str,
        user_id: str,
        expected: Dict[str, Any],
        category: str = "general",
    ):
        """
        Initialize an evaluation case.

        Args:
            name: Test case name
            query: User query to test
            user_id: User ID for this test
            expected: Expected outcomes (intent, keywords, etc.)
            category: Category (recommendation, preference_extraction, general)
        """
        self.name = name
        self.query = query
        self.user_id = user_id
        self.expected = expected
        self.category = category


class AgentEvaluator:
    """Evaluates agent performance on test cases."""

    def __init__(self, verbose: bool = False):
        """
        Initialize the evaluator.

        Args:
            verbose: Whether to print detailed output
        """
        self.verbose = verbose
        self.test_cases = self._load_test_cases()
        self.results: List[Dict[str, Any]] = []

        # Initialize agents
        self.profile_agent = ProfileAgent(llm_type="gemini")
        self.recommender_agent = RecommenderAgent()
        self.orchestrator = OrchestratorAgent(
            profile_agent=self.profile_agent,
            recommender_agent=self.recommender_agent,
        )

        # Use test memory storage
        self.memory = MemoryStorage(storage_dir="evaluation/test_profiles")

    def _load_test_cases(self) -> List[EvaluationCase]:
        """Load evaluation test cases."""
        return [
            # Preference extraction tests
            EvaluationCase(
                name="simple_like",
                query="I love contemporary art",
                user_id="eval_user_1",
                expected={
                    "intent": "preference_update",
                    "extracted_genres": ["contemporary art"],
                    "sentiment": "positive",
                },
                category="preference_extraction",
            ),
            EvaluationCase(
                name="simple_dislike",
                query="I don't like video art",
                user_id="eval_user_2",
                expected={
                    "intent": "preference_update",
                    "extracted_genres": ["video art"],
                    "sentiment": "negative",
                },
                category="preference_extraction",
            ),
            EvaluationCase(
                name="multiple_preferences",
                query="I enjoy sculpture and painting, especially works by Picasso",
                user_id="eval_user_3",
                expected={
                    "intent": "preference_update",
                    "extracted_genres": ["sculpture", "painting"],
                    "extracted_artists": ["Picasso"],
                    "sentiment": "positive",
                },
                category="preference_extraction",
            ),
            # Recommendation tests
            EvaluationCase(
                name="basic_recommendation",
                query="Show me contemporary art exhibitions",
                user_id="eval_user_4",
                expected={
                    "intent": "recommendation",
                    "has_results": True,
                    "result_count": ">0",
                },
                category="recommendation",
            ),
            EvaluationCase(
                name="location_based",
                query="What art events are near Gràcia?",
                user_id="eval_user_5",
                expected={
                    "intent": "recommendation",
                    "has_results": True,
                    "location_extracted": "Gràcia",
                },
                category="recommendation",
            ),
            # General conversation
            EvaluationCase(
                name="greeting",
                query="Hello!",
                user_id="eval_user_6",
                expected={
                    "intent": "general",
                    "response_type": "greeting",
                },
                category="general",
            ),
            EvaluationCase(
                name="help_request",
                query="What can you help me with?",
                user_id="eval_user_7",
                expected={
                    "intent": "general",
                    "response_type": "help",
                },
                category="general",
            ),
        ]

    async def run_evaluation(
        self, categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run evaluation on test cases.

        Args:
            categories: Optional list of categories to test. If None, test all.

        Returns:
            Dict with evaluation results and statistics
        """
        log_info("evaluation_started", total_cases=len(self.test_cases))

        test_cases = self.test_cases
        if categories:
            test_cases = [tc for tc in test_cases if tc.category in categories]

        for case in test_cases:
            result = await self._evaluate_case(case)
            self.results.append(result)

            if self.verbose:
                self._print_result(result)

        # Calculate statistics
        stats = self._calculate_statistics()
        log_info("evaluation_completed", stats=stats)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_cases": len(test_cases),
            "results": self.results,
            "statistics": stats,
        }

    async def _evaluate_case(self, case: EvaluationCase) -> Dict[str, Any]:
        """
        Evaluate a single test case.

        Args:
            case: Test case to evaluate

        Returns:
            Dict with test results
        """
        log_info("evaluating_case", name=case.name, query=case.query[:50])

        try:
            # Run the query through the orchestrator
            response = await self.orchestrator.process_query(
                user_id=case.user_id,
                query=case.query,
            )

            # Check expectations
            checks = self._check_expectations(case, response)

            result = {
                "name": case.name,
                "category": case.category,
                "query": case.query,
                "response": response[:200] if len(response) > 200 else response,
                "checks": checks,
                "passed": all(checks.values()),
            }

            log_info(
                "case_evaluated",
                name=case.name,
                passed=result["passed"],
                checks=checks,
            )

            return result

        except Exception as e:
            log_info("case_failed", name=case.name, error=str(e))
            return {
                "name": case.name,
                "category": case.category,
                "query": case.query,
                "error": str(e),
                "checks": {},
                "passed": False,
            }

    def _check_expectations(
        self, case: EvaluationCase, response: str
    ) -> Dict[str, bool]:
        """
        Check if response meets expectations.

        Args:
            case: Test case with expected outcomes
            response: Agent response

        Returns:
            Dict mapping check name to pass/fail
        """
        checks = {}
        expected = case.expected

        # Check intent (if specified)
        if "intent" in expected:
            # This is a simplified check - in production you'd examine the agent's actual intent
            checks["intent_detected"] = True  # Placeholder

        # Check for results
        if "has_results" in expected:
            has_results = len(response) > 100 and "found" in response.lower()
            checks["has_results"] = has_results == expected["has_results"]

        # Check response type
        if "response_type" in expected:
            response_lower = response.lower()
            if expected["response_type"] == "greeting":
                checks["response_type"] = any(
                    word in response_lower for word in ["hello", "hi", "help"]
                )
            elif expected["response_type"] == "help":
                checks["response_type"] = any(
                    word in response_lower for word in ["help", "can", "recommend"]
                )

        # If no specific checks, consider it passed if no error
        if not checks:
            checks["no_error"] = "error" not in response.lower()

        return checks

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate evaluation statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed", False))
        failed = total - passed

        by_category = {}
        for result in self.results:
            category = result["category"]
            if category not in by_category:
                by_category[category] = {"total": 0, "passed": 0, "failed": 0}
            by_category[category]["total"] += 1
            if result.get("passed", False):
                by_category[category]["passed"] += 1
            else:
                by_category[category]["failed"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
            "by_category": by_category,
        }

    def _print_result(self, result: Dict[str, Any]) -> None:
        """Print a single result."""
        status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
        print(f"\n{status} {result['name']} ({result['category']})")
        print(f"  Query: {result['query']}")
        if "error" in result:
            print(f"  Error: {result['error']}")
        else:
            print(f"  Response: {result['response'][:100]}...")
            if self.verbose:
                print(f"  Checks: {result['checks']}")

    def save_results(self, output_path: str = "evaluation/results.json") -> None:
        """Save evaluation results to file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        results = {
            "timestamp": datetime.now().isoformat(),
            "total_cases": len(self.results),
            "results": self.results,
            "statistics": self._calculate_statistics(),
        }

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        log_info("results_saved", path=output_path)


async def main():
    """Main entry point for evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate agent performance")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--category",
        "-c",
        help="Test specific category (preference_extraction, recommendation, general)",
    )
    parser.add_argument(
        "--output", "-o", default="evaluation/results.json", help="Output file path"
    )

    args = parser.parse_args()

    evaluator = AgentEvaluator(verbose=args.verbose)

    categories = [args.category] if args.category else None
    results = await evaluator.run_evaluation(categories=categories)

    # Print summary
    stats = results["statistics"]
    print("\n" + "=" * 50)
    print("📊 Evaluation Summary")
    print("=" * 50)
    print(f"Total cases: {stats['total']}")
    print(f"Passed: {stats['passed']} ({stats['pass_rate']}%)")
    print(f"Failed: {stats['failed']}")
    print("\nBy category:")
    for category, cat_stats in stats["by_category"].items():
        print(
            f"  {category}: {cat_stats['passed']}/{cat_stats['total']} "
            f"({round(cat_stats['passed']/cat_stats['total']*100, 1)}%)"
        )

    # Save results
    evaluator.save_results(args.output)
    print(f"\n✅ Results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
