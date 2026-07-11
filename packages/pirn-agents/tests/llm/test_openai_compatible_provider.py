"""Tests for :class:`OpenAICompatibleProvider` against a stub HTTP transport.

Covers request shaping, response parsing, error responses, credential config,
native tool-calling (single + parallel), streaming (token + tool-call deltas),
and an end-to-end :class:`ReActLoop` run — all with a fake transport, no
network, and no ``httpx`` import.
"""

from __future__ import annotations

import json
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.toolset import Toolset
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from tests.llm.conftest import FakeAsyncClient, FakeResponse, FakeStream, RecordingSleeper
from tests.specializations.conftest import StubTool


def _chat_completion(content: str = "hello", *, tool_calls: list | None = None) -> FakeResponse:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
        message["content"] = None
    return FakeResponse(
        json_body={
            "choices": [{"message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 6},
        }
    )


def _provider(client: FakeAsyncClient, **kwargs) -> OpenAICompatibleProvider:
    defaults = {
        "model": "test-model",
        "base_url": "https://oai.example/v1",
        "client": client,
        "sleeper": RecordingSleeper(),
    }
    defaults.update(kwargs)
    return OpenAICompatibleProvider(**defaults)


class TestChat(unittest.IsolatedAsyncioTestCase):
    async def test_request_shape_and_endpoint(self) -> None:
        client = FakeAsyncClient(post_results=[_chat_completion()])
        provider = _provider(client, credential=CredentialRef("sk-test"))

        await provider.chat_response(
            [{"role": "user", "content": "hi"}], max_tokens=64, temperature=0.2
        )

        call = client.post_calls[0]
        assert call["url"] == "https://oai.example/v1/chat/completions"
        assert call["headers"]["Authorization"] == "Bearer sk-test"
        assert call["json"]["model"] == "test-model"
        assert call["json"]["max_tokens"] == 64
        assert call["json"]["temperature"] == 0.2
        assert call["json"]["stream"] is False

    async def test_parses_content_finish_and_usage(self) -> None:
        client = FakeAsyncClient(post_results=[_chat_completion("the answer")])
        pricing = ModelPricing(input_per_million=1_000_000.0, output_per_million=1_000_000.0)
        provider = _provider(client, pricing=pricing)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.content == "the answer"
        assert response.finish_reason == "stop"
        assert response.usage == {"input_tokens": 12, "output_tokens": 6}
        # (12 + 6) tokens at 1.0 each = 18 / 1e6 * 1e6 = 18.0
        assert response.cost == 18.0

    async def test_no_auth_header_without_credential(self) -> None:
        client = FakeAsyncClient(post_results=[_chat_completion()])
        provider = _provider(client)

        await provider.chat_response([{"role": "user", "content": "hi"}])

        assert "Authorization" not in client.post_calls[0]["headers"]

    async def test_error_response_raises(self) -> None:
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=404)])
        provider = _provider(client)

        with self.assertRaises(LLMHTTPStatusError):
            await provider.chat_response([{"role": "user", "content": "hi"}])

    async def test_cached_tokens_surface_in_usage(self) -> None:
        client = FakeAsyncClient(
            post_results=[
                FakeResponse(
                    json_body={
                        "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 5,
                            "prompt_tokens_details": {"cached_tokens": 40},
                        },
                    }
                )
            ]
        )
        provider = _provider(client)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.usage["cached_input_tokens"] == 40


class TestToolCalling(unittest.IsolatedAsyncioTestCase):
    async def test_single_tool_call_round_trips(self) -> None:
        tool_calls = [
            {"id": "call-1", "function": {"name": "search", "arguments": json.dumps({"q": "cats"})}}
        ]
        client = FakeAsyncClient(post_results=[_chat_completion(tool_calls=tool_calls)])
        provider = _provider(client)
        toolset = Toolset([StubTool(name="search")])

        response = await provider.chat_response([{"role": "user", "content": "hi"}], tools=toolset)

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].call_id == "call-1"
        assert response.tool_calls[0].arguments == {"q": "cats"}
        # the toolset was encoded into the request
        assert client.post_calls[0]["json"]["tools"][0]["function"]["name"] == "search"

    async def test_parallel_tool_calls_preserve_ids(self) -> None:
        tool_calls = [
            {"id": "a", "function": {"name": "search", "arguments": '{"q": "1"}'}},
            {"id": "b", "function": {"name": "lookup", "arguments": '{"q": "2"}'}},
        ]
        client = FakeAsyncClient(post_results=[_chat_completion(tool_calls=tool_calls)])
        provider = _provider(client)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert [c.call_id for c in response.tool_calls] == ["a", "b"]
        assert [c.tool_name for c in response.tool_calls] == ["search", "lookup"]


class TestStreaming(unittest.IsolatedAsyncioTestCase):
    def _sse(self, chunks: list[dict]) -> list[str]:
        lines = [f"data: {json.dumps(chunk)}" for chunk in chunks]
        lines.append("data: [DONE]")
        return lines

    async def test_streams_tokens_before_completion(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        ]
        stream = FakeStream(lines=self._sse(chunks))
        client = FakeAsyncClient(stream=stream)
        provider = _provider(client)

        contents = []
        async for delta in provider.stream_chat([{"role": "user", "content": "hi"}]):
            if delta.content:
                contents.append(delta.content)
        # tokens were observed as distinct deltas (before the terminal delta)
        assert contents == ["Hel", "lo"]

    async def test_stream_response_accumulates_content_and_usage(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        ]
        client = FakeAsyncClient(stream=FakeStream(lines=self._sse(chunks)))
        provider = _provider(client)

        response = await provider.stream_response([{"role": "user", "content": "hi"}])

        assert response.content == "Hello"
        assert response.usage == {"input_tokens": 3, "output_tokens": 2}

    async def test_streamed_tool_call_deltas_assemble(self) -> None:
        chunks = [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "function": {"name": "search", "arguments": '{"q":'},
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ' "cats"}'}}]}}
                ]
            },
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        ]
        client = FakeAsyncClient(stream=FakeStream(lines=self._sse(chunks)))
        provider = _provider(client)

        response = await provider.stream_response([{"role": "user", "content": "hi"}])

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].call_id == "c1"
        assert response.tool_calls[0].tool_name == "search"
        assert response.tool_calls[0].arguments == {"q": "cats"}


class TestReActLoopEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_react_loop_runs_against_stub_transport(self) -> None:
        client = FakeAsyncClient(
            post_results=[
                _chat_completion("Action: search\nAction Input: foo"),
                _chat_completion("Final Answer: 42 is the answer"),
            ],
            repeat_last=True,
        )
        provider = _provider(client)
        tool = StubTool(name="search", handler="found foo")

        with Tapestry() as tapestry:
            ReActLoop(
                messages=(AgentMessage(role="user", content="What is foo?"),),
                llm=provider,
                tools=(tool,),
                max_iterations=4,
                _config=KnotConfig(id="loop"),
            )
        run = await tapestry.run(RunRequest())

        assert run.succeeded
        response = run.outputs["loop"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "stop"
        assert response.content == "42 is the answer"
        assert tool.invocations == [{"input": "foo"}]


if __name__ == "__main__":
    unittest.main()
