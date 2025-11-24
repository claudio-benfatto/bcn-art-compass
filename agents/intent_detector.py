"""Intent detection interface and implementations.

Provides a standard interface for intent detection and concrete implementations
for different LLM backends (Gemini, Llama/Ollama).
"""

import os
from abc import ABC, abstractmethod
from typing import Literal

from agents.prompts import get_intent_detection_prompt
from observability import log_error, log_info, log_warning

IntentType = Literal["recommendation", "preference_update", "general"]


class IntentDetector(ABC):
    """Abstract base class for intent detection."""

    @abstractmethod
    async def detect_intent(self, query: str) -> IntentType:
        """
        Detect user intent from query.

        Args:
            query: User query text

        Returns:
            Intent type: 'recommendation', 'preference_update', or 'general'

        Raises:
            Exception: If intent detection fails
        """
        pass

    def _get_intent_detection_prompt(self, query: str) -> str:
        """
        Get the prompt for intent detection.

        Args:
            query: User query text

        Returns:
            Formatted prompt string
        """
        return get_intent_detection_prompt(query)

    def _validate_intent(self, intent: str) -> IntentType:
        """
        Validate and normalize intent string.

        Args:
            intent: Raw intent string from LLM

        Returns:
            Validated intent type

        Raises:
            ValueError: If intent is invalid
        """
        normalized = intent.strip().lower()
        if normalized in ["recommendation", "preference_update", "general"]:
            return normalized  # type: ignore
        else:
            raise ValueError(f"Invalid intent: {intent}")


class GeminiIntentDetector(IntentDetector):
    """Intent detector using Google Gemini."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini intent detector.

        Args:
            api_key: Google API key
            model: Gemini model to use (default: gemini-2.5-flash)
        """
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        log_info("intent_detector_initialized", backend="gemini", model=model)

    async def detect_intent(self, query: str) -> IntentType:
        """Detect intent using Gemini."""
        prompt = self._get_intent_detection_prompt(query)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt
            )

            intent = self._validate_intent(response.text)
            log_info("gemini_intent_detected", query=query[:50], intent=intent)
            return intent

        except ValueError as e:
            log_warning(
                "gemini_intent_invalid",
                query=query[:50],
                error=str(e),
            )
            raise

        except Exception as e:
            log_error(
                "gemini_intent_detection_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise


class OllamaIntentDetector(IntentDetector):
    """Intent detector using Ollama (local Llama)."""

    def __init__(self, model: str = "llama3.2:3b"):
        """
        Initialize Ollama intent detector.

        Args:
            model: Ollama model to use
        """
        import ollama

        # Test if Ollama is available
        ollama.list()
        
        self.client = ollama
        self.model = model
        log_info("intent_detector_initialized", backend="ollama", model=model)

    async def detect_intent(self, query: str) -> IntentType:
        """Detect intent using Ollama."""
        prompt = self._get_intent_detection_prompt(query)

        try:
            response = await self.client.chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                options={
                    'temperature': 0.1,
                    'num_predict': 10,  # We only need one word
                }
            )

            intent = self._validate_intent(response['message']['content'])
            log_info("llama_intent_detected", query=query[:50], intent=intent, model=self.model)
            return intent

        except ValueError as e:
            log_warning(
                "llama_intent_invalid",
                query=query[:50],
                error=str(e),
            )
            raise

        except Exception as e:
            log_error(
                "llama_intent_detection_failed",
                error=str(e),
                error_type=type(e).__name__,
                model=self.model,
            )
            raise


def create_intent_detector() -> IntentDetector:
    """
    Factory function to create intent detector based on environment.

    Prefers Gemini if GOOGLE_API_KEY is set, otherwise tries Ollama.

    Returns:
        IntentDetector instance

    Raises:
        RuntimeError: If no suitable intent detector can be created
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if api_key:
        return GeminiIntentDetector(api_key=api_key)
    
    # Try Ollama
    try:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        return OllamaIntentDetector(model=model)
    except Exception as e:
        log_error(
            "intent_detector_creation_failed",
            error=str(e),
            error_type=type(e).__name__,
            message="No suitable intent detector available"
        )
        raise RuntimeError(
            "Intent detection requires either GOOGLE_API_KEY (for Gemini) "
            "or Ollama (for local Llama). Please configure one of these options."
        ) from e
