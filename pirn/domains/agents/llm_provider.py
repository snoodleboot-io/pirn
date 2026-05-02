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
        raise NotImplementedError(
            f"{type(self).__name__} must implement chat()"
        )

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield streamed chat-completion chunks for ``messages``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement stream_chat()"
        )

    async def close(self) -> None:
        """Release any underlying connections / resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )
