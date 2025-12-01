"""Preference extraction interface and implementations.

Provides a standard interface for extracting user preferences from natural language
using different LLM backends (Gemini or rule-based fallback).
"""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Protocol

from agents.prompts import get_preference_extraction_prompt
from observability import log_error, log_info


class PreferenceExtractor(ABC):
    """Abstract base class for preference extraction."""

    @abstractmethod
    async def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract preferences from natural language text.

        Args:
            text: User text expressing preferences

        Returns:
            Dict with keys: favorite_genres, disliked_genres, favorite_artists, location

        Raises:
            Exception: If extraction fails
        """
        pass


class RuleBasedExtractor(PreferenceExtractor):
    """Rule-based preference extraction using keyword matching."""

    async def extract(self, text: str) -> Dict[str, Any]:
        """Extract preferences using simple rule-based patterns."""
        text_lower = text.lower()
        result: Dict[str, Any] = {
            "favorite_genres": [],
            "disliked_genres": [],
            "favorite_artists": [],
            "location": None
        }

        # Common art genres
        genres = [
            "contemporary art", "modern art", "abstract art", "sculpture",
            "painting", "photography", "video art", "performance art",
            "installation", "digital art", "street art", "conceptual art"
        ]

        # Detect likes
        like_patterns = [
            r"i (love|like|enjoy|prefer|am into)",
            r"i'?m (interested in|a fan of)",
            r"my favorite.* (is|are)"
        ]

        # Detect dislikes
        dislike_patterns = [
            r"i (don'?t|do not) (like|enjoy)",
            r"i (hate|dislike)",
            r"not (a fan|interested in)",
        ]

        # Extract genres
        for genre in genres:
            if genre in text_lower:
                # Check if it's a like or dislike
                for pattern in like_patterns:
                    if re.search(pattern + r".*" + re.escape(genre), text_lower):
                        result["favorite_genres"].append(genre)
                        break
                else:
                    for pattern in dislike_patterns:
                        if re.search(pattern + r".*" + re.escape(genre), text_lower):
                            result["disliked_genres"].append(genre)
                            break

        log_info("rule_based_extraction_complete", extracted_genres=len(result["favorite_genres"] + result["disliked_genres"]))
        return result


class PreferenceLlmClient(Protocol):
    """Minimal protocol for an LLM client used for preference extraction."""

    def generate_json(self, prompt: str) -> str:  # pragma: no cover - interface definition
        ...


def _strip_json_code_fences(result_text: str) -> str:
    """Strip optional ```json/``` code fences from an LLM JSON response."""
    text = result_text.strip()

    if text.startswith("```json"):
        text = text[len("```json") :]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


class GeminiPreferenceExtractor(PreferenceExtractor):
    """Preference extractor using Google Gemini."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        client: PreferenceLlmClient | None = None,
    ):
        """
        Initialize Gemini preference extractor.

        Args:
            api_key: Google API key
            model: Gemini model to use
            client: Optional pre-configured PreferenceLlmClient (for testing or custom wiring)
        """
        self.model = model
        if client is not None:
            self._client = client
        else:
            # Import inside to avoid hard dependency during tests that inject a fake client
            from google import genai  # type: ignore[import-not-found]

            self._client = genai.Client(api_key=api_key)

        log_info("preference_extractor_initialized", backend="gemini", model=model)

    async def extract(self, text: str) -> Dict[str, Any]:
        """Extract preferences using Gemini."""
        prompt = get_preference_extraction_prompt(text)

        try:
            # Call underlying client (can be real Gemini or injected fake)
            if isinstance(self._client, object) and hasattr(self._client, "models"):
                # google-genai client path
                raw_text = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                ).text
                result_text = (raw_text or "").strip()
            else:
                # Protocol-based client (tests) implements generate_json directly
                result_text = self._client.generate_json(prompt)  # type: ignore[union-attr]

            # Clean up response (remove markdown code blocks if present)
            cleaned = _strip_json_code_fences(result_text)

            # Parse JSON
            extracted: Dict[str, Any] = json.loads(cleaned)
            log_info("gemini_preference_extraction_success", has_favorites=len(extracted.get("favorite_genres", [])) > 0)
            return extracted

        except json.JSONDecodeError as e:
            log_error(
                "gemini_preference_extraction_json_error",
                error=str(e),
                error_type="JSONDecodeError",
                response_text=result_text[:100]
            )
            raise

        except Exception as e:
            log_error(
                "gemini_preference_extraction_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise


def create_preference_extractor(fallback_to_rules: bool = True) -> PreferenceExtractor:
    """
    Factory function to create preference extractor based on environment.

    Prefers Gemini if GOOGLE_API_KEY is set otherwise falls back to rule-based extraction.
    Falls back to rule-based if requested and no LLM is available.

    Args:
        fallback_to_rules: Whether to fallback to rule-based extraction if no LLM is available

    Returns:
        PreferenceExtractor instance

    Raises:
        RuntimeError: If no suitable extractor can be created and fallback is disabled
    """
    api_key = os.getenv("GOOGLE_API_KEY")

    if api_key:
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return GeminiPreferenceExtractor(api_key=api_key, model=model)

    elif fallback_to_rules:
        log_info(
            "preference_extractor_fallback",
            message="No LLM available, using rule-based extraction",
        )
        return RuleBasedExtractor()
 
    raise RuntimeError(
        "Preference extraction requires GOOGLE_API_KEY (for Gemini) of fallback_to_rules set to True"
        "Please configure one of these options."
    )
