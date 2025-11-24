"""Tests for IntentDetector interface and implementations.

Tests both Gemini and Llama (via Ollama) intent detection methods.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.intent_detector import (
    GeminiIntentDetector,
    OllamaIntentDetector,
    create_intent_detector,
)
from agents.orchestrator import OrchestratorAgent


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock()
    store.query.return_value = []
    return store


class TestGeminiIntentDetection:
    """Test Gemini-based intent detection."""

    @pytest.mark.asyncio
    async def test_recommendation_intent(self):
        """Test detection of recommendation intent."""
        detector = GeminiIntentDetector(api_key="test-key")

        # Mock the async generate_content method
        mock_response = Mock()
        mock_response.text = "recommendation"
        detector.client = Mock()
        detector.client.aio = Mock()
        detector.client.aio.models = Mock()
        detector.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        intent = await detector.detect_intent("Show me contemporary art exhibitions")
        assert intent == "recommendation"

    @pytest.mark.asyncio
    async def test_preference_update_intent(self):
        """Test detection of preference update intent."""
        detector = GeminiIntentDetector(api_key="test-key")

        mock_response = Mock()
        mock_response.text = "preference_update"
        detector.client = Mock()
        detector.client.aio = Mock()
        detector.client.aio.models = Mock()
        detector.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        intent = await detector.detect_intent("I love sculpture")
        assert intent == "preference_update"

    @pytest.mark.asyncio
    async def test_general_intent(self):
        """Test detection of general intent."""
        detector = GeminiIntentDetector(api_key="test-key")

        mock_response = Mock()
        mock_response.text = "general"
        detector.client = Mock()
        detector.client.aio = Mock()
        detector.client.aio.models = Mock()
        detector.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        intent = await detector.detect_intent("Hello, how are you?")
        assert intent == "general"

    @pytest.mark.asyncio
    async def test_invalid_response_raises_error(self):
        """Test that invalid Gemini response raises error."""
        detector = GeminiIntentDetector(api_key="test-key")

        mock_response = Mock()
        mock_response.text = "invalid_intent"
        detector.client = Mock()
        detector.client.aio = Mock()
        detector.client.aio.models = Mock()
        detector.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="Invalid intent"):
            await detector.detect_intent("Show me exhibitions")

    @pytest.mark.asyncio
    async def test_api_error_raises_error(self):
        """Test that API error is raised."""
        detector = GeminiIntentDetector(api_key="test-key")

        detector.client = Mock()
        detector.client.aio = Mock()
        detector.client.aio.models = Mock()
        detector.client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API error")
        )

        with pytest.raises(Exception, match="API error"):
            await detector.detect_intent("I love modern art")

    def test_factory_creates_gemini_when_api_key_available(self):
        """Test that factory creates Gemini detector when API key is available."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            detector = create_intent_detector()
            assert isinstance(detector, GeminiIntentDetector)


class TestOllamaIntentDetection:
    """Test Llama (Ollama) intent detection."""

    @pytest.mark.asyncio
    async def test_recommendation_intent(self):
        """Test detection of recommendation intent with Llama."""
        # Mock ollama.list() to avoid connection error
        with patch('ollama.list', return_value=[]):
            detector = OllamaIntentDetector()

            # Mock ollama client
            mock_ollama = Mock()
            mock_ollama.chat = AsyncMock(return_value={
                'message': {'content': 'recommendation'}
            })
            detector.client = mock_ollama

            intent = await detector.detect_intent("Show me contemporary art exhibitions")
            assert intent == "recommendation"

    @pytest.mark.asyncio
    async def test_preference_update_intent(self):
        """Test detection of preference update intent with Llama."""
        with patch('ollama.list', return_value=[]):
            detector = OllamaIntentDetector()

            mock_ollama = Mock()
            mock_ollama.chat = AsyncMock(return_value={
                'message': {'content': 'preference_update'}
            })
            detector.client = mock_ollama

            intent = await detector.detect_intent("I love sculpture")
            assert intent == "preference_update"

    @pytest.mark.asyncio
    async def test_general_intent(self):
        """Test detection of general intent with Llama."""
        with patch('ollama.list', return_value=[]):
            detector = OllamaIntentDetector()

            mock_ollama = Mock()
            mock_ollama.chat = AsyncMock(return_value={
                'message': {'content': 'general'}
            })
            detector.client = mock_ollama

            intent = await detector.detect_intent("Hello, how are you?")
            assert intent == "general"

    @pytest.mark.asyncio
    async def test_invalid_response_raises_error(self):
        """Test that invalid Llama response raises error."""
        with patch('ollama.list', return_value=[]):
            detector = OllamaIntentDetector()

            mock_ollama = Mock()
            mock_ollama.chat = AsyncMock(return_value={
                'message': {'content': 'invalid_intent'}
            })
            detector.client = mock_ollama

            with pytest.raises(ValueError, match="Invalid intent"):
                await detector.detect_intent("Show me exhibitions")

    @pytest.mark.asyncio
    async def test_ollama_error_raises_error(self):
        """Test that Ollama error is raised."""
        with patch('ollama.list', return_value=[]):
            detector = OllamaIntentDetector()

            mock_ollama = Mock()
            mock_ollama.chat = AsyncMock(side_effect=Exception("Connection error"))
            detector.client = mock_ollama

            with pytest.raises(Exception, match="Connection error"):
                await detector.detect_intent("I love modern art")

    def test_factory_creates_ollama_when_no_api_key(self):
        """Test that factory creates Ollama detector when no API key."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock ollama module being available
            mock_ollama = Mock()
            mock_ollama.list = Mock(return_value=[])
            with patch.dict('sys.modules', {'ollama': mock_ollama}):
                detector = create_intent_detector()
                assert isinstance(detector, OllamaIntentDetector)

    def test_custom_ollama_model(self):
        """Test that custom Ollama model can be specified."""
        with patch('ollama.list', return_value=[]):
            detector = OllamaIntentDetector(model="llama3.2:1b")
            assert detector.model == "llama3.2:1b"


class TestNoLLMAvailable:
    """Test behavior when no LLM is available."""

    def test_factory_raises_runtime_error(self):
        """Test that factory raises RuntimeError when no LLM is available."""
        import builtins

        with patch.dict(os.environ, {}, clear=True):
            # Mock ollama import to fail
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == 'ollama':
                    raise ImportError("No module named 'ollama'")
                return original_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=mock_import):
                with pytest.raises(RuntimeError, match="Intent detection requires"):
                    create_intent_detector()


class TestIntentDetectionIntegration:
    """Integration tests for intent detection in full pipeline."""

    @pytest.mark.asyncio
    async def test_recommendation_flow_with_gemini(self, mock_vector_store):
        """Test full recommendation flow with Gemini intent detection."""
        # Create a mock intent detector
        mock_detector = Mock()
        mock_detector.detect_intent = AsyncMock(return_value="recommendation")

        with patch("agents.orchestrator._create_vector_store", return_value=mock_vector_store):
            agent = OrchestratorAgent(intent_detector=mock_detector)

            # Mock recommender agent
            agent.recommender_agent.recommend = Mock(return_value=[])
            agent.recommender_agent.format_recommendations = Mock(return_value="No events found")

            response = await agent.process_query("Show me exhibitions", user_id="test_user")

            # Verify intent detector was called
            mock_detector.detect_intent.assert_called_once_with("Show me exhibitions")
            # Verify recommender was called
            agent.recommender_agent.recommend.assert_called_once()
            assert "No events found" in response

    @pytest.mark.asyncio
    async def test_preference_flow_with_gemini(self, mock_vector_store):
        """Test full preference update flow with Gemini intent detection."""
        # Create a mock intent detector
        mock_detector = Mock()
        mock_detector.detect_intent = AsyncMock(return_value="preference_update")

        with patch("agents.orchestrator._create_vector_store", return_value=mock_vector_store):
            agent = OrchestratorAgent(intent_detector=mock_detector)

            # Mock profile agent
            from memory.models import UserProfile
            mock_profile = UserProfile(user_id="test_user")
            mock_profile.favorite_genres = ["contemporary art"]

            agent.profile_agent.extract_preferences = AsyncMock(return_value=mock_profile)

            response = await agent.process_query("I love contemporary art", user_id="test_user")

            # Verify intent detector was called
            mock_detector.detect_intent.assert_called_once_with("I love contemporary art")
            # Verify profile agent was called
            agent.profile_agent.extract_preferences.assert_called_once()
            assert "updated your preferences" in response

    @pytest.mark.asyncio
    async def test_general_flow_with_gemini(self, mock_vector_store):
        """Test fallback response with Gemini intent detection."""
        # Create a mock intent detector
        mock_detector = Mock()
        mock_detector.detect_intent = AsyncMock(return_value="general")

        with patch("agents.orchestrator._create_vector_store", return_value=mock_vector_store):
            agent = OrchestratorAgent(intent_detector=mock_detector)

            response = await agent.process_query("Hello", user_id="test_user")

            # Verify intent detector was called
            mock_detector.detect_intent.assert_called_once_with("Hello")
            # Verify fallback response
            assert "I'm here to help you discover cultural events" in response

    @pytest.mark.asyncio
    async def test_recommendation_flow_with_llama(self, mock_vector_store):
        """Test full recommendation flow with Llama intent detection."""
        # Create a mock intent detector
        mock_detector = Mock()
        mock_detector.detect_intent = AsyncMock(return_value="recommendation")

        with patch("agents.orchestrator._create_vector_store", return_value=mock_vector_store):
            agent = OrchestratorAgent(intent_detector=mock_detector)

            # Mock recommender agent
            agent.recommender_agent.recommend = Mock(return_value=[])
            agent.recommender_agent.format_recommendations = Mock(return_value="No events found")

            response = await agent.process_query("Show me exhibitions", user_id="test_user")

            # Verify intent detector was called
            mock_detector.detect_intent.assert_called_once_with("Show me exhibitions")
            # Verify recommender was called
            agent.recommender_agent.recommend.assert_called_once()
            assert "No events found" in response


class TestPromptGeneration:
    """Test intent detection prompt generation."""

    def test_prompt_contains_categories(self):
        """Test that prompt contains all intent categories."""
        detector = GeminiIntentDetector(api_key="test-key")
        prompt = detector._get_intent_detection_prompt("test query")

        assert "recommendation" in prompt
        assert "preference_update" in prompt
        assert "general" in prompt

    def test_prompt_contains_examples(self):
        """Test that prompt contains examples."""
        detector = GeminiIntentDetector(api_key="test-key")
        prompt = detector._get_intent_detection_prompt("test query")

        assert "Show me contemporary art exhibitions" in prompt
        assert "I love sculpture" in prompt
        assert "Hello" in prompt

    def test_prompt_contains_query(self):
        """Test that prompt contains the user query."""
        detector = GeminiIntentDetector(api_key="test-key")
        test_query = "Find museums near me"
        prompt = detector._get_intent_detection_prompt(test_query)

        assert test_query in prompt
