"""Interface for asynchronous LLM chat backends.

Concrete providers (Anthropic, OpenAI, local engines, stub doubles)
inherit from :class:`LLMProvider` and implement :meth:`chat`,
:meth:`stream_chat`, and :meth:`close`. Pirn agent knots depend only on
this interface; the provider is constructed by the user and passed in
as a config value.

Pydantic treats providers as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity-keyed serialiser keeps content-addressing cache stable
without descending into vendor SDKs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class LLMProvider(PirnOpaqueValue):
    """Interface every async LLM provider must satisfy."""

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        """Send a chat completion request and return the raw response.

        ``messages`` is a sequence of role/content mappings (the chat
        wire format used by Anthropic/OpenAI-compatible APIs).
        """
        raise NotImplementedError(f"{type(self).__name__} must implement chat()")

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield streamed chat-completion chunks for ``messages``."""
        raise NotImplementedError(f"{type(self).__name__} must implement stream_chat()")

    async def close(self) -> None:
        """Release any underlying connections / resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    @property
    def prompt_cache_enabled(self) -> bool:
        """Whether this provider caches large, stable prompt prefixes server-side.

        Default ``False``. A provider with native prompt caching overrides this to
        ``True`` and implements :meth:`mark_prompt_cache`.
        """
        return False

    def mark_prompt_cache(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> Sequence[Mapping[str, Any]]:
        """Annotate ``messages`` for the provider's native prompt cache.

        Only meaningful when :attr:`prompt_cache_enabled` is ``True``; the default
        raises since a base provider has no native cache to mark.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support prompt caching")

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the provider.

        Concrete implementations should call this from ``close()`` after
        tearing down the live SDK / client. It nulls ``self._config`` so
        the credential string (token, api key, secret) becomes garbage-
        collectable as soon as the caller drops the provider reference.
        Long-running processes that hold provider references after
        ``close()`` benefit; default deployments are unaffected.
        """
        self._config = None
