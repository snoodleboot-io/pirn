"""``PromptCachePassthrough`` — defer to a provider's native prompt cache when present.

Some providers cache large, stable prompt prefixes server-side. When a provider
exposes that capability there is nothing to gain (and correctness to lose) from
re-caching the same prompt locally, so this helper *asks* the provider — via the
declared :attr:`~pirn_agents.llm_provider.LLMProvider.prompt_cache_enabled`
capability, provider-neutral with no vendor import — and passes the prompt
through untouched, reporting that the provider owns caching. When the provider
has no native support the helper reports so, and the caller falls back to a
local :class:`~pirn_agents.caching.result_cache.ResultCache`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.llm_provider import LLMProvider


class PromptCachePassthrough:
    """Route prompt caching to a provider's native mechanism, else signal fallback."""

    @staticmethod
    def supports_native(provider: LLMProvider) -> bool:
        """Return whether ``provider`` owns prompt caching natively.

        Reads the declared :attr:`LLMProvider.prompt_cache_enabled` capability —
        no ``getattr`` probing and no vendor SDK import.
        """
        return provider.prompt_cache_enabled

    @staticmethod
    def passthrough(
        provider: LLMProvider, messages: Sequence[Mapping[str, Any]]
    ) -> tuple[Sequence[Mapping[str, Any]], bool]:
        """Prepare ``messages`` for ``provider``, deferring to native caching if any.

        Args:
            provider: The LLM provider the messages are bound for.
            messages: The prompt messages to send.

        Returns:
            A ``(messages, used_native)`` pair. When ``used_native`` is ``True``
            the provider owns caching (messages annotated by its
            :meth:`LLMProvider.mark_prompt_cache` hook) and the caller must NOT
            cache locally. When ``False`` no native cache exists and the caller
            should apply a local :class:`ResultCache`.
        """
        if not provider.prompt_cache_enabled:
            return messages, False
        return provider.mark_prompt_cache(messages), True
