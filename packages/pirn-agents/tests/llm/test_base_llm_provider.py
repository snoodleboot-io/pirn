"""Unit tests for :class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider`.

Exercises the shared cross-cutting behaviour (retries/backoff, distinct 429
handling, transient/transport retries, non-retryable errors, response mapping,
usage + cost accounting, and streaming connection cleanup) through a minimal
``StubLLMProvider`` subclass driven by a fake HTTP transport — no network, no
``httpx`` import.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.rate_limit_error import RateLimitError
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.provider_adapter import ProviderAdapter
from pirn_agents.toolset import Toolset
from tests.llm.conftest import FakeAsyncClient, FakeResponse, FakeStream, RecordingSleeper


class _StubToolAdapter(ProviderAdapter):
    """Trivial adapter: the provider message is already a list of call dicts."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        return dict(neutral_tool)

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        return list(provider_msg)

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        return dict(result_payload)


class StubLLMProvider(BaseLLMProvider):
    """Minimal concrete provider over a tiny made-up wire shape."""

    def _tool_adapter(self) -> ProviderAdapter:
        return _StubToolAdapter()

    def _completions_path(self) -> str:
        return "/complete"

    def _auth_headers(self) -> dict[str, str]:
        if self._credential is None:
            return {}
        return {"x-key": self._credential.reveal()}

    def _build_request(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        tools: Toolset | None,
    ) -> dict[str, Any]:
        return {"model": model or self._model, "messages": list(messages), "stream": stream}

    def _content_text(self, data: Mapping[str, Any]) -> str:
        text = data.get("text")
        return text if isinstance(text, str) else ""

    def _tool_message(self, data: Mapping[str, Any]) -> Any:
        return data.get("tool_calls") or []

    def _finish_reason(self, data: Mapping[str, Any]) -> str:
        return str(data.get("stop", "stop"))

    def _usage_tokens(self, data: Mapping[str, Any]) -> dict[str, int]:
        usage = data.get("usage") or {}
        return {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
        }

    async def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        async for line in response.aiter_lines():
            yield StreamDelta(content=line)


def _ok_response(**overrides: Any) -> FakeResponse:
    body: dict[str, Any] = {
        "text": "hello",
        "tool_calls": [],
        "stop": "stop",
        "usage": {"input_tokens": 10, "output_tokens": 4},
    }
    body.update(overrides)
    return FakeResponse(status_code=200, json_body=body)


def _make_provider(client: FakeAsyncClient, **kwargs: Any) -> StubLLMProvider:
    defaults: dict[str, Any] = {
        "model": "stub-model",
        "base_url": "https://stub.example/v1",
        "client": client,
        "sleeper": RecordingSleeper(),
        "rng": lambda: 1.0,
    }
    defaults.update(kwargs)
    return StubLLMProvider(**defaults)


class TestResponseMapping(unittest.IsolatedAsyncioTestCase):
    async def test_maps_raw_response_to_agent_response(self) -> None:
        client = FakeAsyncClient(post_results=[_ok_response()])
        provider = _make_provider(client)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.content == "hello"
        assert response.finish_reason == "stop"
        assert response.usage == {"input_tokens": 10, "output_tokens": 4}
        assert response.tool_calls == ()

    async def test_chat_returns_normalised_mapping_with_content(self) -> None:
        client = FakeAsyncClient(post_results=[_ok_response()])
        provider = _make_provider(client)

        result = await provider.chat([{"role": "user", "content": "hi"}])

        assert result["content"] == "hello"
        assert result["finish_reason"] == "stop"
        assert result["usage"] == {"input_tokens": 10, "output_tokens": 4}

    async def test_cost_estimated_when_pricing_configured(self) -> None:
        client = FakeAsyncClient(post_results=[_ok_response()])
        pricing = ModelPricing(input_per_million=1000.0, output_per_million=2000.0)
        provider = _make_provider(client, pricing=pricing)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        # (10 * 1000 + 4 * 2000) / 1e6 = 18000 / 1e6 = 0.018
        assert response.cost == 0.018

    async def test_cost_is_none_without_pricing(self) -> None:
        client = FakeAsyncClient(post_results=[_ok_response()])
        provider = _make_provider(client)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.cost is None

    async def test_decodes_tool_calls(self) -> None:
        body_calls = [{"id": "c1", "name": "search", "arguments": {"q": "cats"}}]
        client = FakeAsyncClient(
            post_results=[_ok_response(tool_calls=body_calls, stop="tool_use")]
        )
        provider = _make_provider(client)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].call_id == "c1"
        assert response.tool_calls[0].tool_name == "search"
        assert response.tool_calls[0].arguments == {"q": "cats"}

    async def test_auth_header_uses_credential(self) -> None:
        client = FakeAsyncClient(post_results=[_ok_response()])
        provider = _make_provider(client, credential=CredentialRef("secret-key"))

        await provider.chat_response([{"role": "user", "content": "hi"}])

        assert client.post_calls[0]["headers"]["x-key"] == "secret-key"
        assert client.post_calls[0]["url"] == "https://stub.example/v1/complete"


class TestRetryAndRateLimit(unittest.IsolatedAsyncioTestCase):
    async def test_429_is_retried_and_honours_retry_after(self) -> None:
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(
            post_results=[
                FakeResponse(status_code=429, headers={"retry-after": "1.5"}),
                _ok_response(),
            ]
        )
        provider = _make_provider(client, sleeper=sleeper)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.content == "hello"
        assert sleeper.delays == [1.5]

    async def test_429_without_retry_after_uses_backoff(self) -> None:
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=429), _ok_response()])
        provider = _make_provider(
            client,
            sleeper=sleeper,
            retry_policy=RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=10.0, jitter=False),
        )

        await provider.chat_response([{"role": "user", "content": "hi"}])

        assert sleeper.delays == [0.1]

    async def test_429_exhausts_retries_and_raises(self) -> None:
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=429) for _ in range(3)])
        provider = _make_provider(
            client,
            sleeper=sleeper,
            retry_policy=RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=10.0, jitter=False),
        )

        with self.assertRaises(RateLimitError):
            await provider.chat_response([{"role": "user", "content": "hi"}])
        # max_retries=2 -> two backoff sleeps before the final failure.
        assert sleeper.delays == [0.1, 0.2]

    async def test_5xx_is_retried_as_transient(self) -> None:
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=503), _ok_response()])
        provider = _make_provider(client, sleeper=sleeper)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.content == "hello"
        assert len(sleeper.delays) == 1

    async def test_transport_error_is_wrapped_and_retried(self) -> None:
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "httpx"
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(post_results=[ReadTimeout("timed out"), _ok_response()])
        provider = _make_provider(client, sleeper=sleeper)

        response = await provider.chat_response([{"role": "user", "content": "hi"}])

        assert response.content == "hello"
        assert len(sleeper.delays) == 1

    async def test_non_retryable_4xx_raises_immediately(self) -> None:
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=400)])
        provider = _make_provider(client, sleeper=sleeper)

        with self.assertRaises(LLMHTTPStatusError):
            await provider.chat_response([{"role": "user", "content": "hi"}])
        assert sleeper.delays == []

    def test_transport_error_detection_is_httpx_scoped(self) -> None:
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "httpx"

        class ValueErrorLike(Exception):
            pass

        ValueErrorLike.__module__ = "builtins"

        assert BaseLLMProvider._is_transient_transport_error(ReadTimeout()) is True
        assert BaseLLMProvider._is_transient_transport_error(ValueErrorLike()) is False


class TestStreamingCleanup(unittest.IsolatedAsyncioTestCase):
    async def test_stream_yields_tokens_and_accumulates(self) -> None:
        stream = FakeStream(lines=["He", "llo"])
        client = FakeAsyncClient(stream=stream)
        provider = _make_provider(client)

        deltas = [d async for d in provider.stream_chat([{"role": "user", "content": "hi"}])]

        assert [d.content for d in deltas] == ["He", "llo"]
        response = await provider.collect_stream(_as_aiter(deltas))
        assert response.content == "Hello"

    async def test_stream_closed_on_early_cancellation(self) -> None:
        stream = FakeStream(lines=["a", "b", "c"])
        client = FakeAsyncClient(stream=stream)
        provider = _make_provider(client)

        agen = provider.stream_chat([{"role": "user", "content": "hi"}])
        first = await agen.__anext__()
        assert first.content == "a"
        await agen.aclose()

        assert stream.closed is True

    async def test_stream_closed_on_mid_stream_error(self) -> None:
        stream = FakeStream(lines=["a", "b"], raise_after=1)
        client = FakeAsyncClient(stream=stream)
        provider = _make_provider(client)

        with self.assertRaises(RuntimeError):
            async for _ in provider.stream_chat([{"role": "user", "content": "hi"}]):
                pass

        assert stream.closed is True

    async def test_stream_error_status_raises_and_closes(self) -> None:
        stream = FakeStream(status_code=500, lines=[])
        client = FakeAsyncClient(stream=stream)
        provider = _make_provider(client)

        with self.assertRaises(LLMHTTPStatusError):
            async for _ in provider.stream_chat([{"role": "user", "content": "hi"}]):
                pass

        assert stream.closed is True


async def _as_aiter(items: list[StreamDelta]) -> AsyncIterator[StreamDelta]:
    for item in items:
        yield item


if __name__ == "__main__":
    unittest.main()
