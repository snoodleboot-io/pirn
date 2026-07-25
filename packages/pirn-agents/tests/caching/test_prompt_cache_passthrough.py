"""Mirrored tests for :class:`PromptCachePassthrough` native-vs-fallback routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from pirn_agents.caching.prompt_cache_passthrough import PromptCachePassthrough
from pirn_agents.llm_provider import LLMProvider


class _PlainProvider(LLMProvider):
    """A provider with no native prompt caching (inherits the default)."""


class _FlagProvider(LLMProvider):
    """A provider whose native cache needs no per-message annotation."""

    @property
    def prompt_cache_enabled(self) -> bool:
        return True

    def mark_prompt_cache(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> Sequence[Mapping[str, Any]]:
        return messages


class _MarkerProvider(LLMProvider):
    """A provider that annotates messages for native caching."""

    @property
    def prompt_cache_enabled(self) -> bool:
        return True

    def mark_prompt_cache(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> Sequence[Mapping[str, Any]]:
        return [{**m, "cache": True} for m in messages]


class TestSupportsNative:
    def test_plain_provider_unsupported(self) -> None:
        assert PromptCachePassthrough.supports_native(_PlainProvider()) is False

    def test_flag_provider_supported(self) -> None:
        assert PromptCachePassthrough.supports_native(_FlagProvider()) is True

    def test_marker_provider_supported(self) -> None:
        assert PromptCachePassthrough.supports_native(_MarkerProvider()) is True

    def test_base_mark_prompt_cache_raises(self) -> None:
        # An enabled provider must implement the hook; the base refuses silently.
        with pytest.raises(NotImplementedError):
            LLMProvider().mark_prompt_cache([{"role": "user", "content": "hi"}])


class TestPassthrough:
    def test_fallback_when_unsupported(self) -> None:
        passthrough = PromptCachePassthrough()
        messages = [{"role": "user", "content": "hi"}]
        out, used_native = passthrough.passthrough(_PlainProvider(), messages)
        assert used_native is False
        assert out is messages  # unchanged; caller applies a local cache

    def test_flag_provider_passes_through_unchanged(self) -> None:
        passthrough = PromptCachePassthrough()
        messages = [{"role": "user", "content": "hi"}]
        out, used_native = passthrough.passthrough(_FlagProvider(), messages)
        assert used_native is True
        assert out == messages

    def test_marker_provider_annotates(self) -> None:
        passthrough = PromptCachePassthrough()
        messages = [{"role": "user", "content": "hi"}]
        out, used_native = passthrough.passthrough(_MarkerProvider(), messages)
        assert used_native is True
        assert out == [{"role": "user", "content": "hi", "cache": True}]
