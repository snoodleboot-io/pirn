"""Tests for the F20 structured-output extension of the F3 providers.

Exercises the capability surface and ``structured_chat`` request merging on the
real :class:`OpenAICompatibleProvider` / :class:`AnthropicMessagesProvider`
through the hermetic fake HTTP transport — proving the extension threads native
request options into the wire payload without disturbing existing shaping.
"""

from __future__ import annotations

import unittest

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from tests.llm.conftest import FakeAsyncClient, FakeResponse


def _openai_completion() -> FakeResponse:
    return FakeResponse(
        json_body={
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
    )


class TestOpenAICompatibleStructuredOutput(unittest.IsolatedAsyncioTestCase):
    async def test_capability_advertises_all_native_paths(self) -> None:
        provider = OpenAICompatibleProvider(model="m", base_url="https://x/v1")

        capability = provider.structured_output_capability()

        assert capability.native_schema is True
        assert capability.forced_tool_choice is True
        assert capability.constrained_decoding is True

    async def test_structured_chat_merges_response_format_into_payload(self) -> None:
        client = FakeAsyncClient(post_results=[_openai_completion()])
        provider = OpenAICompatibleProvider(model="m", base_url="https://x/v1", client=client)
        options = provider.native_schema_option({"type": "object"}, name="Rec")

        response = await provider.structured_chat(
            [{"role": "user", "content": "hi"}], request_options=options
        )

        assert response.content == '{"ok": true}'
        posted = client.post_calls[0]["json"]
        assert posted["response_format"]["json_schema"]["name"] == "Rec"
        # Existing shaping is preserved.
        assert posted["messages"] == [{"role": "user", "content": "hi"}]
        assert posted["model"] == "m"

    async def test_structured_chat_without_options_matches_plain_request(self) -> None:
        client = FakeAsyncClient(post_results=[_openai_completion()])
        provider = OpenAICompatibleProvider(model="m", base_url="https://x/v1", client=client)

        await provider.structured_chat([{"role": "user", "content": "hi"}])

        posted = client.post_calls[0]["json"]
        assert "response_format" not in posted
        assert "tool_choice" not in posted

    async def test_merge_request_options_deep_merges_extra_body(self) -> None:
        merged = OpenAICompatibleProvider._merge_request_options(
            {"model": "m", "extra_body": {"a": 1}},
            {"extra_body": {"b": 2}, "tool_choice": "x"},
        )

        assert merged["extra_body"] == {"a": 1, "b": 2}
        assert merged["tool_choice"] == "x"
        assert merged["model"] == "m"

    async def test_forced_tool_choice_option_shape(self) -> None:
        provider = OpenAICompatibleProvider(model="m", base_url="https://x/v1")

        assert provider.forced_tool_choice_option("extract") == {
            "tool_choice": {"type": "function", "function": {"name": "extract"}}
        }

    async def test_constrained_decoding_option_maps_guided_fields(self) -> None:
        provider = OpenAICompatibleProvider(model="m", base_url="https://x/v1")

        options = provider.constrained_decoding_option(
            {"json_schema": {"type": "object"}, "regex": "^a$"}
        )

        assert options["extra_body"]["guided_json"] == {"type": "object"}
        assert options["extra_body"]["guided_regex"] == "^a$"


class TestAnthropicMessagesStructuredOutput(unittest.IsolatedAsyncioTestCase):
    async def test_capability_advertises_forced_tool_choice_only(self) -> None:
        provider = AnthropicMessagesProvider(model="m", base_url="https://x")

        capability = provider.structured_output_capability()

        assert capability.forced_tool_choice is True
        assert capability.native_schema is False
        assert capability.constrained_decoding is False

    async def test_forced_tool_choice_option_uses_messages_shape(self) -> None:
        provider = AnthropicMessagesProvider(model="m", base_url="https://x")

        assert provider.forced_tool_choice_option("extract") == {
            "tool_choice": {"type": "tool", "name": "extract"}
        }

    async def test_native_schema_option_raises_when_unadvertised(self) -> None:
        provider = AnthropicMessagesProvider(model="m", base_url="https://x")

        with self.assertRaises(NotImplementedError):
            provider.native_schema_option({"type": "object"}, name="Rec")


if __name__ == "__main__":
    unittest.main()
