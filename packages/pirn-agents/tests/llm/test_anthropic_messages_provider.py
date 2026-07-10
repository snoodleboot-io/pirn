"""Tests for :class:`AnthropicMessagesProvider` against a stub HTTP transport.

Covers the distinct Messages-API request/response shape, native tool-calling,
streaming via typed SSE events, and the opt-in prompt-caching hook — all with a
fake transport, no network, and no ``httpx`` import.
"""

from __future__ import annotations

import json
import unittest

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.toolset import Toolset
from tests.llm.conftest import FakeAsyncClient, FakeResponse, FakeStream, RecordingSleeper
from tests.specializations.conftest import StubTool


def _message_response(**overrides) -> FakeResponse:
    body = {
        "content": [{"type": "text", "text": "hello"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 3},
    }
    body.update(overrides)
    return FakeResponse(json_body=body)


def _provider(client: FakeAsyncClient, **kwargs) -> AnthropicMessagesProvider:
    defaults = {
        "model": "messages-model",
        "base_url": "https://msg.example/v1",
        "client": client,
        "sleeper": RecordingSleeper(),
    }
    defaults.update(kwargs)
    return AnthropicMessagesProvider(**defaults)


class TestChat(unittest.IsolatedAsyncioTestCase):
    async def test_endpoint_headers_and_system_extraction(self) -> None:
        client = FakeAsyncClient(post_results=[_message_response()])
        provider = _provider(client, credential=CredentialRef("api-secret"))

        await provider.chat_response(
            [
                {"role": "system", "content": "be terse"},
                {"role": "user", "content": "hi"},
            ]
        )

        call = client.post_calls[0]
        assert call["url"] == "https://msg.example/v1/messages"
        assert call["headers"]["x-api-key"] == "api-secret"
        assert call["headers"]["anthropic-version"] == "2023-06-01"
        assert call["json"]["system"] == "be terse"
        assert call["json"]["messages"] == [{"role": "user", "content": "hi"}]
        # max_tokens is required by this API and defaulted when unset.
        assert call["json"]["max_tokens"] == 1024

    async def test_parses_text_finish_and_usage(self) -> None:
        client = FakeAsyncClient(post_results=[_message_response()])
        provider = _provider(client, pricing=ModelPricing(output_per_million=1_000_000.0))

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.content == "hello"
        assert response.finish_reason == "stop"
        assert response.usage == {"input_tokens": 10, "output_tokens": 3}
        assert response.cost == 3.0

    async def test_tool_use_response_decodes_and_maps_finish(self) -> None:
        client = FakeAsyncClient(
            post_results=[
                _message_response(
                    content=[
                        {"type": "text", "text": "looking"},
                        {"type": "tool_use", "id": "tu1", "name": "search", "input": {"q": "cats"}},
                    ],
                    stop_reason="tool_use",
                )
            ]
        )
        provider = _provider(client)
        toolset = Toolset([StubTool(name="search")])

        response = await provider.chat_response([{"role": "user", "content": "hi"}], tools=toolset)

        assert response.finish_reason == "tool_use"
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].call_id == "tu1"
        assert response.tool_calls[0].arguments == {"q": "cats"}
        # tools were encoded in the distinct input_schema shape
        assert client.post_calls[0]["json"]["tools"][0]["input_schema"]["type"] == "object"

    async def test_cached_tokens_surface_in_usage(self) -> None:
        client = FakeAsyncClient(
            post_results=[
                _message_response(
                    usage={
                        "input_tokens": 100,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 60,
                    }
                )
            ]
        )
        provider = _provider(client)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.usage["cached_input_tokens"] == 60


class TestPromptCachingHook(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_leaves_system_as_plain_string(self) -> None:
        client = FakeAsyncClient(post_results=[_message_response()])
        provider = _provider(client, enable_prompt_cache=False)

        await provider.chat_response(
            [{"role": "system", "content": "ctx"}, {"role": "user", "content": "hi"}]
        )

        assert client.post_calls[0]["json"]["system"] == "ctx"

    async def test_enabled_marks_system_with_cache_control(self) -> None:
        client = FakeAsyncClient(post_results=[_message_response()])
        provider = _provider(client, enable_prompt_cache=True)

        await provider.chat_response(
            [{"role": "system", "content": "ctx"}, {"role": "user", "content": "hi"}]
        )

        system = client.post_calls[0]["json"]["system"]
        assert system == [{"type": "text", "text": "ctx", "cache_control": {"type": "ephemeral"}}]


class TestStreaming(unittest.IsolatedAsyncioTestCase):
    def _sse(self, events: list[dict]) -> list[str]:
        return [f"data: {json.dumps(event)}" for event in events]

    async def test_streams_text_tokens_and_usage(self) -> None:
        events = [
            {
                "type": "message_start",
                "message": {"usage": {"input_tokens": 10, "output_tokens": 0}},
            },
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hel"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "lo"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 2},
            },
            {"type": "message_stop"},
        ]
        client = FakeAsyncClient(stream=FakeStream(lines=self._sse(events)))
        provider = _provider(client)

        response = await provider.stream_response([{"role": "user", "content": "hi"}])

        assert response.content == "Hello"
        assert response.finish_reason == "stop"
        assert response.usage == {"input_tokens": 10, "output_tokens": 2}
        # text block stop must not create a spurious tool call
        assert response.tool_calls == ()

    async def test_streamed_tool_use_deltas_assemble(self) -> None:
        events = [
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "tu1", "name": "search"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"q": '},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '"cats"}'},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"output_tokens": 7},
            },
        ]
        client = FakeAsyncClient(stream=FakeStream(lines=self._sse(events)))
        provider = _provider(client)

        response = await provider.stream_response([{"role": "user", "content": "hi"}])

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].call_id == "tu1"
        assert response.tool_calls[0].tool_name == "search"
        assert response.tool_calls[0].arguments == {"q": "cats"}
        assert response.finish_reason == "tool_use"


if __name__ == "__main__":
    unittest.main()
