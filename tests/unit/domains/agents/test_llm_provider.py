"""Unit tests for :class:`LLMProvider`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.domains.agents.llm_provider import LLMProvider


class _ConcreteLLM(LLMProvider):
    async def chat(self, messages, *, model=None, max_tokens=None, temperature=None):
        return {"role": "assistant", "content": "hello"}

    async def stream_chat(self, messages, *, model=None, max_tokens=None, temperature=None):
        async def _aiter():
            yield {"content": "hello"}
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
            await provider.stream_chat([])

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
