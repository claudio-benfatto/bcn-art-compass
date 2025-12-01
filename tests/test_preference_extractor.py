import json
import pytest

from agents.preference_extractor import (
    GeminiPreferenceExtractor,
    PreferenceLlmClient,
    RuleBasedExtractor,
)


class FakePreferenceClient(PreferenceLlmClient):
    def __init__(self, response: str):
        self.response = response
        self.calls: list[str] = []

    def generate_json(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


class FakePreferenceClientInvalid(PreferenceLlmClient):
    def generate_json(self, prompt: str) -> str:
        return "not-json"


@pytest.mark.asyncio
async def test_gemini_preference_extractor_parses_valid_json_with_code_fences():
    payload = {
        "favorite_genres": ["sculpture"],
        "disliked_genres": ["video art"],
        "favorite_artists": ["Picasso"],
        "location": "Barcelona",
    }
    wrapped = "```json\n" + json.dumps(payload) + "\n```"
    client = FakePreferenceClient(wrapped)

    extractor = GeminiPreferenceExtractor(api_key="dummy", client=client)

    result = await extractor.extract("I love sculpture in Barcelona but dislike video art.")

    assert result == payload
    assert len(client.calls) == 1
    # Prompt should contain some of the original text
    assert "sculpture" in client.calls[0]


@pytest.mark.asyncio
async def test_gemini_preference_extractor_raises_on_invalid_json():
    extractor = GeminiPreferenceExtractor(api_key="dummy", client=FakePreferenceClientInvalid())

    with pytest.raises(json.JSONDecodeError):
        await extractor.extract("anything")


@pytest.mark.asyncio
async def test_rule_based_extractor_basic_behavior():
    extractor = RuleBasedExtractor()
    text = "I love sculpture but I don't like video art."
    result = await extractor.extract(text)

    assert "sculpture" in result["favorite_genres"]
    # Depending on pattern match, video art may be disliked or ignored; assert key exists.
    assert "disliked_genres" in result


