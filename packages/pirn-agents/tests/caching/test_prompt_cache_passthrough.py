"""Mirrored tests for :class:`PromptCachePassthrough` native-vs-fallback routing."""

from __future__ import annotations

from typing import Any

from pirn_agents.caching.prompt_cache_passthrough import PromptCachePassthrough


class _PlainProvider:
    """A provider with no native prompt caching."""


class _FlagProvider:
    """A provider that advertises native caching via a truthy attribute."""

    prompt_cache_enabled = True


class _MarkerProvider:
    """A provider that annotates messages for native caching."""

    def mark_prompt_cache(self, messages: Any) -> list[dict[str, Any]]:
        return [{**m, "cache": True} for m in messages]


class TestSupportsNative:
    def test_plain_provider_unsupported(self) -> None:
        assert PromptCachePassthrough.supports_native(_PlainProvider()) is False

    def test_flag_provider_supported(self) -> None:
        assert PromptCachePassthrough.supports_native(_FlagProvider()) is True

    def test_marker_provider_supported(self) -> None:
        assert PromptCachePassthrough.supports_native(_MarkerProvider()) is True


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
