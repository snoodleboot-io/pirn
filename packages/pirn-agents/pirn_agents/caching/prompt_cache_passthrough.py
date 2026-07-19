"""``PromptCachePassthrough`` — defer to a provider's native prompt cache when present.

Some providers cache large, stable prompt prefixes server-side. When a provider
exposes that capability there is nothing to gain (and correctness to lose) from
re-caching the same prompt locally, so this helper detects the capability via the
provider's declared :attr:`~pirn.core.providers.llm_provider.LLMProvider.prompt_cache_enabled`
flag and passes the prompt through untouched, reporting that the provider owns
caching. When the provider has no native support the helper reports so, and the
caller falls back to a local
:class:`~pirn_agents.caching.result_cache.ResultCache`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider


class PromptCachePassthrough:
    """Route prompt caching to a provider's native mechanism, else signal fallback."""

    @staticmethod
    def supports_native(provider: LLMProvider) -> bool:
        """Return whether ``provider`` exposes a native prompt cache.

        The capability is the provider's declared ``prompt_cache_enabled`` flag;
        no vendor SDK is imported to make this decision.
        """
        return provider.prompt_cache_enabled

    def passthrough(
        self, provider: LLMProvider, messages: Sequence[Any]
    ) -> tuple[Sequence[Any], bool]:
        """Prepare ``messages`` for ``provider``, deferring to native caching if any.

        Args:
            provider: The LLM provider the messages are bound for.
            messages: The prompt messages to send.

        Returns:
            A ``(messages, used_native)`` pair. When ``used_native`` is ``True``
            the provider owns caching (messages annotated by its
            ``mark_prompt_cache`` hook) and the caller must NOT cache locally.
            When ``False`` no native cache exists and the caller should apply a
            local :class:`ResultCache`.
        """
        if not self.supports_native(provider):
            return messages, False
        return provider.mark_prompt_cache(messages), True
