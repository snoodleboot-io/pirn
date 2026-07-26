"""``HttpStructuredOutputProvider`` — the HTTP base that carries the F20 seam.

An HTTP provider base that combines the cross-cutting machinery of
:class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider` (retries, response
mapping, streaming, cost accounting) with the native structured-output seam of
:class:`pirn_agents.specializations.structured_output.structured_output_provider.StructuredOutputProvider`.

The plain :class:`BaseLLMProvider` stays thin — it exposes no structured-output
surface, so plain-chat consumers never depend on it (ISP). HTTP providers that
*do* support one of the native single-pass mechanisms subclass **this** base
instead: it implements :meth:`structured_chat` once (shaping the request through
the same hooks as plain chat, then merging the strategy's ``request_options``),
while the three ``*_option`` shapers and the capability advertisement are
inherited from ``StructuredOutputProvider`` — where the base shapers raise
:class:`NotImplementedError` so a provider that advertises a mechanism it never
implements fails loudly. The unified decoder gates on
``isinstance(llm, StructuredOutputProvider)``, so an instance of this class
crosses into the native paths while a bare ``BaseLLMProvider`` does not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)
from pirn_agents.tools.toolset import Toolset
from pirn_agents.types.messaging.agent_response import AgentResponse


class HttpStructuredOutputProvider(BaseLLMProvider, StructuredOutputProvider):
    """HTTP provider base carrying the native structured-output seam."""

    async def structured_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
        request_options: Mapping[str, Any] | None = None,
    ) -> AgentResponse:
        """Send a chat completion merging ``request_options`` into the request.

        Identical to :meth:`BaseLLMProvider.chat_response` but for the extra
        ``request_options`` (a native ``response_format`` / ``tool_choice`` /
        constrained-decoding fragment produced by an F20 strategy), which are
        merged into the shaped request body. When ``request_options`` is empty
        the request is byte-for-byte the same as ``chat_response``, so existing
        behavior is unchanged.
        """
        payload = self._build_request(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            tools=tools,
        )
        self._apply_prompt_cache(payload)
        if request_options:
            payload = self._merge_request_options(payload, request_options)
        return await self._complete(payload)

    @staticmethod
    def _merge_request_options(
        payload: dict[str, Any], request_options: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Merge ``request_options`` into ``payload``, deep-merging ``extra_body``.

        Top-level keys are overlaid onto the payload; ``extra_body`` (used by
        local engines for guided-decoding fields) is merged one level deep so a
        strategy's constraint keys join, rather than clobber, any existing ones.
        """
        merged = dict(payload)
        for key, value in request_options.items():
            if key == "extra_body" and isinstance(value, Mapping):
                existing = merged.get("extra_body")
                base = dict(existing) if isinstance(existing, Mapping) else {}
                merged["extra_body"] = {**base, **dict(value)}
            else:
                merged[key] = value
        return merged
