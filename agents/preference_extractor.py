"""Preference extraction interface and implementations.

Provides a standard interface for extracting user preferences from natural language
using different LLM backends (Gemini, Llama/Ollama, or rule-based fallback).
"""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Dict

from agents.prompts import get_preference_extraction_prompt
from observability import log_error, log_info


class PreferenceExtractor(ABC):
    """Abstract base class for preference extraction."""

    @abstractmethod
    async def extract(self, text: str) -> Dict[str, any]:
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

    async def extract(self, text: str) -> Dict[str, any]:
        """Extract preferences using simple rule-based patterns."""
        text_lower = text.lower()
        result = {
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


class GeminiPreferenceExtractor(PreferenceExtractor):
    """Preference extractor using Google Gemini."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini preference extractor.

        Args:
            api_key: Google API key
            model: Gemini model to use
        """
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        log_info("preference_extractor_initialized", backend="gemini", model=model)

    async def extract(self, text: str) -> Dict[str, any]:
        """Extract preferences using Gemini."""
        prompt = get_preference_extraction_prompt(text)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result_text = response.text.strip()

            # Clean up response (remove markdown code blocks if present)
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            # Parse JSON
            extracted = json.loads(result_text)
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


class OllamaPreferenceExtractor(PreferenceExtractor):
    """Preference extractor using Ollama (local Llama)."""

    def __init__(self, model: str = "llama3.2"):
        """
        Initialize Ollama preference extractor.

        Args:
            model: Ollama model to use
        """
        import ollama

        # Test if Ollama is available
        ollama.list()

        self.client = ollama
        self.model = model
        log_info("preference_extractor_initialized", backend="ollama", model=model)

    async def extract(self, text: str) -> Dict[str, any]:
        """Extract preferences using Ollama."""
        prompt = get_preference_extraction_prompt(text)

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response["message"]["content"].strip()

            # Clean up response
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            # Parse JSON
            extracted = json.loads(result_text)
            log_info("ollama_preference_extraction_success", has_favorites=len(extracted.get("favorite_genres", [])) > 0)
            return extracted

        except json.JSONDecodeError as e:
            log_error(
                "ollama_preference_extraction_json_error",
                error=str(e),
                error_type="JSONDecodeError",
                response_text=result_text[:100]
            )
            raise

        except Exception as e:
            log_error(
                "ollama_preference_extraction_failed",
                error=str(e),
                error_type=type(e).__name__,
                model=self.model,
            )
            raise


def create_preference_extractor(fallback_to_rules: bool = True) -> PreferenceExtractor:
    """
    Factory function to create preference extractor based on environment.

    Prefers Gemini if GOOGLE_API_KEY is set, otherwise tries Ollama.
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

    # Try Ollama
    try:
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        return OllamaPreferenceExtractor(model=model)
    except Exception as e:
        if fallback_to_rules:
            log_info(
                "preference_extractor_fallback",
                message="No LLM available, using rule-based extraction",
                reason=str(e)
            )
            return RuleBasedExtractor()
        else:
            log_error(
                "preference_extractor_creation_failed",
                error=str(e),
                error_type=type(e).__name__,
                message="No suitable preference extractor available"
            )
            raise RuntimeError(
                "Preference extraction requires either GOOGLE_API_KEY (for Gemini) "
                "or Ollama (for local Llama). Please configure one of these options."
            ) from e
