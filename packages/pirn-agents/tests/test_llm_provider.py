"""Unit tests for pirn-agents' :class:`LLMProvider` (PIR-735: domain-owned)."""

from __future__ import annotations

import unittest

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta


class _ConcreteLLM(LLMProvider):
    async def chat(self, messages, *, model=None, max_tokens=None, temperature=None):
        return {"role": "assistant", "content": "hello"}

    def stream_chat(self, messages, *, model=None, max_tokens=None, temperature=None):
        async def _aiter():
            yield StreamDelta(content="hello")

        return _aiter()

    async def close(self) -> None:
        self._clear_credentials()


class TestLLMProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_chat_raises_not_implemented(self) -> None:
        provider = LLMProvider()
        with self.assertRaises(NotImplementedError):
            await provider.chat([])

    async def test_stream_chat_raises_not_implemented(self) -> None:
        provider = LLMProvider()
        with self.assertRaises(NotImplementedError):
            provider.stream_chat([])

    async def test_close_raises_not_implemented(self) -> None:
        provider = LLMProvider()
        with self.assertRaises(NotImplementedError):
            await provider.close()

    async def test_concrete_chat_returns_mapping(self) -> None:
        llm = _ConcreteLLM()
        result = await llm.chat([{"role": "user", "content": "hi"}])
        assert result["content"] == "hello"

    async def test_clear_credentials_nulls_config(self) -> None:
        llm = _ConcreteLLM()
        await llm.close()
        assert llm._config is None


class TestStreamChatShape(unittest.TestCase):
    """``stream_chat`` is an iterator factory, not a coroutine (PIR-833).

    The interface used to declare it ``async def``, so a caller written against
    :class:`LLMProvider` would ``await`` the call — which raises ``TypeError``
    against every shipped provider, all of which implement it as an async
    generator. These assertions pin the shape on both sides of the contract.
    """

    def test_interface_declaration_is_not_a_coroutine_function(self) -> None:
        import inspect

        assert not inspect.iscoroutinefunction(LLMProvider.stream_chat)

    def test_shipped_base_provider_is_an_async_generator_function(self) -> None:
        import inspect

        from pirn_agents.llm.base_llm_provider import BaseLLMProvider

        assert inspect.isasyncgenfunction(BaseLLMProvider.stream_chat)

    def test_concrete_double_returns_an_iterator_without_awaiting(self) -> None:
        stream = _ConcreteLLM().stream_chat([{"role": "user", "content": "hi"}])
        assert hasattr(stream, "__anext__")
