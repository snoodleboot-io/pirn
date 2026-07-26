"""Characterisation tests for the neutral finish-reason vocabulary.

The framework's neutral terminal vocabulary is ``stop`` / ``length`` /
``tool_use`` / ``content_filter``; ``TerminationCheck`` and ~25 response
constructors compare against those spellings. Each provider owns the mapping
from *its* wire values onto them — neither vendor's spelling is the neutral one
by fiat.

These cases pin both providers symmetrically, including the pass-through of
genuinely unknown vendor values.
"""

from __future__ import annotations

import json
import unittest

from pirn.security.credential_ref import CredentialRef

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.types.messaging.agent_response import AgentResponse
from pirn_agents.types.messaging.finish_reason import FinishReason
from tests.llm.conftest import FakeAsyncClient, FakeResponse, FakeStream, RecordingSleeper


def _chat_completion(finish_reason: str | None) -> FakeResponse:
    """Return a chat-completions body carrying ``finish_reason``."""
    choice: dict = {"message": {"role": "assistant", "content": "hi"}}
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    return FakeResponse(json_body={"choices": [choice]})


def _messages_response(stop_reason: object) -> FakeResponse:
    """Return a Messages-API body carrying ``stop_reason``."""
    return FakeResponse(
        json_body={
            "content": [{"type": "text", "text": "hi"}],
            "stop_reason": stop_reason,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )


def _openai(client: FakeAsyncClient) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        model="test-model",
        base_url="https://example.invalid/v1",
        client=client,
        sleeper=RecordingSleeper(),
        credential=CredentialRef("k"),
    )


def _messages(client: FakeAsyncClient) -> AnthropicMessagesProvider:
    return AnthropicMessagesProvider(
        model="test-model",
        base_url="https://example.invalid",
        client=client,
        sleeper=RecordingSleeper(),
        credential=CredentialRef("k"),
    )


def _sse(chunks: list[dict]) -> list[str]:
    """Render chat-completions SSE lines (terminated by the ``[DONE]`` sentinel)."""
    return [f"data: {json.dumps(chunk)}" for chunk in chunks] + ["data: [DONE]"]


def _messages_sse(events: list[dict]) -> list[str]:
    """Render Messages-API SSE lines (typed events, no ``[DONE]`` sentinel)."""
    return [f"data: {json.dumps(event)}" for event in events]


class TestMessagesWireMapping(unittest.IsolatedAsyncioTestCase):
    async def test_end_turn_maps_to_stop(self) -> None:
        # Arrange / Act / Assert
        provider = _messages(FakeAsyncClient(post_results=[_messages_response("end_turn")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "stop"

    async def test_max_tokens_maps_to_length(self) -> None:
        # Arrange / Act / Assert
        provider = _messages(FakeAsyncClient(post_results=[_messages_response("max_tokens")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "length"

    async def test_tool_use_maps_to_tool_use(self) -> None:
        # Arrange / Act / Assert
        provider = _messages(FakeAsyncClient(post_results=[_messages_response("tool_use")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "tool_use"

    async def test_unknown_wire_value_passes_through(self) -> None:
        # Arrange / Act / Assert: an unmapped vendor value is surfaced verbatim
        # rather than silently coerced to a neutral member.
        provider = _messages(FakeAsyncClient(post_results=[_messages_response("stop_sequence")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "stop_sequence"

    async def test_missing_wire_value_defaults_to_stop(self) -> None:
        # Arrange / Act / Assert
        provider = _messages(FakeAsyncClient(post_results=[_messages_response(None)]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "stop"


class TestChatCompletionsWireMapping(unittest.IsolatedAsyncioTestCase):
    async def test_stop_maps_to_stop(self) -> None:
        # Arrange / Act / Assert
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion("stop")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "stop"

    async def test_length_maps_to_length(self) -> None:
        # Arrange / Act / Assert
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion("length")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "length"

    async def test_tool_calls_maps_to_tool_use(self) -> None:
        # Arrange: the chat-completions terminal for "the model wants tools".
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion("tool_calls")]))

        # Act
        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        # Assert: normalised onto the neutral member the rest of the framework
        # consumes — previously leaked out as the raw wire value "tool_calls".
        assert response.finish_reason == "tool_use"

    async def test_function_call_maps_to_tool_use(self) -> None:
        # Arrange / Act / Assert: the legacy spelling normalises identically.
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion("function_call")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "tool_use"

    async def test_content_filter_maps_to_content_filter(self) -> None:
        # Arrange / Act / Assert
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion("content_filter")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "content_filter"

    async def test_unknown_wire_value_passes_through(self) -> None:
        # Arrange / Act / Assert
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion("weird_reason")]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "weird_reason"

    async def test_missing_wire_value_defaults_to_stop(self) -> None:
        # Arrange / Act / Assert
        provider = _openai(FakeAsyncClient(post_results=[_chat_completion(None)]))
        response = await provider.chat_response([{"role": "user", "content": "hi"}])
        assert response.finish_reason == "stop"


class TestStreamingNormalisation(unittest.IsolatedAsyncioTestCase):
    async def test_chat_completions_stream_normalises_tool_calls(self) -> None:
        # Arrange: the streamed terminal chunk carries the raw wire value.
        chunks = [{"choices": [{"delta": {"content": "x"}, "finish_reason": "tool_calls"}]}]
        provider = _openai(FakeAsyncClient(stream=FakeStream(lines=_sse(chunks))))

        # Act
        response = await provider.stream_response([{"role": "user", "content": "hi"}])

        # Assert: the streaming path normalises exactly like the buffered one.
        assert response.finish_reason == "tool_use"

    async def test_messages_stream_normalises_end_turn(self) -> None:
        # Arrange
        events = [
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "x"},
            },
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
        ]
        provider = _messages(FakeAsyncClient(stream=FakeStream(lines=_messages_sse(events))))

        # Act
        response = await provider.stream_response([{"role": "user", "content": "hi"}])

        # Assert
        assert response.finish_reason == "stop"


class TestFinishReasonEnum(unittest.TestCase):
    def test_values_are_plain_strings(self) -> None:
        # Arrange / Act / Assert: the str mixin keeps `==` against raw literals working,
        # so the ~25 AgentResponse(finish_reason="stop") call sites are unaffected.
        assert FinishReason.STOP == "stop"
        assert FinishReason.LENGTH == "length"
        assert FinishReason.TOOL_USE == "tool_use"
        assert FinishReason.CONTENT_FILTER == "content_filter"

    def test_agent_response_defaults_to_stop(self) -> None:
        # Arrange / Act / Assert
        assert AgentResponse(content="x").finish_reason == "stop"
        assert AgentResponse(content="x").finish_reason == FinishReason.STOP

    def test_both_providers_agree_on_the_tool_terminal(self) -> None:
        # Arrange / Act / Assert: the two wire spellings converge on one neutral
        # member — neither vendor's spelling wins by being checked first.
        assert AnthropicMessagesProvider._map_stop_reason("tool_use") == FinishReason.TOOL_USE
        assert OpenAICompatibleProvider._map_finish_reason("tool_calls") == FinishReason.TOOL_USE

    def test_both_providers_agree_on_the_length_terminal(self) -> None:
        # Arrange / Act / Assert
        assert AnthropicMessagesProvider._map_stop_reason("max_tokens") == FinishReason.LENGTH
        assert OpenAICompatibleProvider._map_finish_reason("length") == FinishReason.LENGTH

    def test_both_providers_agree_on_the_natural_stop(self) -> None:
        # Arrange / Act / Assert
        assert AnthropicMessagesProvider._map_stop_reason("end_turn") == FinishReason.STOP
        assert OpenAICompatibleProvider._map_finish_reason("stop") == FinishReason.STOP

    def test_both_providers_default_a_missing_value_to_stop(self) -> None:
        # Arrange / Act / Assert
        assert AnthropicMessagesProvider._map_stop_reason(None) == FinishReason.STOP
        assert OpenAICompatibleProvider._map_finish_reason(None) == FinishReason.STOP
        assert OpenAICompatibleProvider._map_finish_reason("") == FinishReason.STOP


if __name__ == "__main__":
    unittest.main()
