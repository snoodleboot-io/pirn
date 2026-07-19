"""Mirrored tests for :class:`PromptCachePassthrough` native-vs-fallback routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.caching.prompt_cache_passthrough import PromptCachePassthrough


class _PlainProvider(LLMProvider):
    """A provider with no native prompt caching (inherits the default flag)."""


class _FlagProvider(LLMProvider):
    """A provider that advertises native caching and annotates messages for it."""

    prompt_cache_enabled = True

    def mark_prompt_cache(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> Sequence[Mapping[str, Any]]:
        return [{**m, "cache": True} for m in messages]


class TestSupportsNative:
    def test_plain_provider_unsupported(self) -> None:
        assert PromptCachePassthrough.supports_native(_PlainProvider()) is False

    def test_flag_provider_supported(self) -> None:
        assert PromptCachePassthrough.supports_native(_FlagProvider()) is True


class TestPassthrough:
    def test_fallback_when_unsupported(self) -> None:
        passthrough = PromptCachePassthrough()
        messages = [{"role": "user", "content": "hi"}]
        out, used_native = passthrough.passthrough(_PlainProvider(), messages)
        assert used_native is False
        assert out is messages  # unchanged; caller applies a local cache

    def test_flag_provider_annotates_via_native(self) -> None:
        passthrough = PromptCachePassthrough()
        messages = [{"role": "user", "content": "hi"}]
        out, used_native = passthrough.passthrough(_FlagProvider(), messages)
        assert used_native is True
        assert out == [{"role": "user", "content": "hi", "cache": True}]
