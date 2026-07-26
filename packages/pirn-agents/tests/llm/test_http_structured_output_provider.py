"""Unit tests for
:class:`pirn_agents.llm.http_structured_output_provider.HttpStructuredOutputProvider`.

Proves the HTTP seam carries the F20 structured-output surface: it is nominally
a :class:`StructuredOutputProvider` (so the unified decoder's ``isinstance``
probe routes it native) *and* a :class:`BaseLLMProvider` (so it reuses the shared
transport/mapping machinery). Drives ``structured_chat`` through the hermetic
fake transport and checks the ``request_options`` merge, then confirms the
un-overridden option shapers inherit the loud ``NotImplementedError`` base.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.http_structured_output_provider import HttpStructuredOutputProvider
from pirn_agents.llm.provider_adapter import ProviderAdapter
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)
from pirn_agents.tools.toolset import Toolset
from tests.llm.conftest import FakeAsyncClient, FakeResponse


class _StubToolAdapter(ProviderAdapter):
    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        return dict(neutral_tool)

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        return list(provider_msg)

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        return dict(result_payload)


class _StubStructuredProvider(HttpStructuredOutputProvider):
    """Minimal HTTP structured provider echoing the shaped body back in tests."""

    def _tool_adapter(self) -> ProviderAdapter:
        return _StubToolAdapter()

    def _completions_path(self) -> str:
        return "/complete"

    def _auth_headers(self) -> dict[str, str]:
        return {}

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
        return {}

    async def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        async for line in response.aiter_lines():
            yield StreamDelta(content=line)


def _ok() -> FakeResponse:
    return FakeResponse(status_code=200, json_body={"text": "hi", "tool_calls": [], "stop": "stop"})


def _make(client: FakeAsyncClient) -> _StubStructuredProvider:
    return _StubStructuredProvider(
        model="stub-model", base_url="https://stub.example/v1", client=client
    )


class TestSeamLineage(unittest.TestCase):
    def test_is_structured_output_provider_and_base_llm_provider(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(HttpStructuredOutputProvider, StructuredOutputProvider)
        assert issubclass(HttpStructuredOutputProvider, BaseLLMProvider)

    def test_capability_defaults_to_advertise_nothing(self) -> None:
        # Arrange
        provider = _make(FakeAsyncClient())

        # Act
        capability = provider.structured_output_capability()

        # Assert: inherits the advertise-nothing safe default (happy path, no raise).
        assert capability == StructuredOutputCapability()


class TestStructuredChat(unittest.IsolatedAsyncioTestCase):
    async def test_merges_request_options_into_payload(self) -> None:
        # Arrange
        client = FakeAsyncClient(post_results=[_ok()])
        provider = _make(client)

        # Act
        response = await provider.structured_chat(
            [{"role": "user", "content": "hi"}],
            request_options={"response_format": {"type": "json"}},
        )

        # Assert
        assert response.content == "hi"
        posted = client.post_calls[0]["json"]
        assert posted["response_format"] == {"type": "json"}
        assert posted["messages"] == [{"role": "user", "content": "hi"}]

    async def test_without_options_matches_plain_shaping(self) -> None:
        # Arrange
        client = FakeAsyncClient(post_results=[_ok()])
        provider = _make(client)

        # Act
        await provider.structured_chat([{"role": "user", "content": "hi"}])

        # Assert
        posted = client.post_calls[0]["json"]
        assert "response_format" not in posted

    async def test_unadvertised_option_shaper_raises_loudly(self) -> None:
        # Arrange
        provider = _make(FakeAsyncClient())

        # Act / Assert: inherited NotImplementedError base names the concrete class.
        with self.assertRaisesRegex(NotImplementedError, "_StubStructuredProvider"):
            provider.native_schema_option({}, name="x")


class TestMergeRequestOptions(unittest.TestCase):
    def test_deep_merges_extra_body(self) -> None:
        # Arrange / Act
        merged = HttpStructuredOutputProvider._merge_request_options(
            {"model": "m", "extra_body": {"a": 1}},
            {"extra_body": {"b": 2}, "tool_choice": "x"},
        )

        # Assert
        assert merged["extra_body"] == {"a": 1, "b": 2}
        assert merged["tool_choice"] == "x"
        assert merged["model"] == "m"


if __name__ == "__main__":
    unittest.main()
