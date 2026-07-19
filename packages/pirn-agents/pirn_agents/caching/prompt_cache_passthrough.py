"""``PromptCachePassthrough`` — defer to a provider's native prompt cache when present.

Some providers cache large, stable prompt prefixes server-side. When a provider
exposes that capability there is nothing to gain (and correctness to lose) from
re-caching the same prompt locally, so this helper *detects* the capability by
duck-typing — provider-neutral, no vendor import at module load — and passes the
prompt through untouched, reporting that the provider owns caching. When the
provider has no native support the helper reports so, and the caller falls back
to a local :class:`~pirn_agents.caching.result_cache.ResultCache`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast


class PromptCachePassthrough:
    """Route prompt caching to a provider's native mechanism, else signal fallback."""

    @staticmethod
    def supports_native(provider: Any) -> bool:
        """Return whether ``provider`` exposes a native prompt cache.

        Provider-neutral duck typing: a truthy ``prompt_cache_enabled`` attribute
        or a callable ``mark_prompt_cache`` method counts as native support. No
        vendor SDK is imported to make this decision.
        """
        if getattr(provider, "prompt_cache_enabled", False):
            return True
        return callable(getattr(provider, "mark_prompt_cache", None))

    def passthrough(self, provider: Any, messages: Sequence[Any]) -> tuple[Sequence[Any], bool]:
        """Prepare ``messages`` for ``provider``, deferring to native caching if any.

        Args:
            provider: The LLM provider the messages are bound for.
            messages: The prompt messages to send.

        Returns:
            A ``(messages, used_native)`` pair. When ``used_native`` is ``True``
            the provider owns caching (messages annotated by its
            ``mark_prompt_cache`` hook if it has one, else passed through
            unchanged) and the caller must NOT cache locally. When ``False`` no
            native cache exists and the caller should apply a local
            :class:`ResultCache`.
        """
        if not self.supports_native(provider):
            return messages, False
        marker: Any = getattr(provider, "mark_prompt_cache", None)
        if callable(marker):
            return cast("Sequence[Any]", marker(messages)), True
        return messages, True
