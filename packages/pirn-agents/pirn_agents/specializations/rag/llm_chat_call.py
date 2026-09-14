# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``LLMChatCall`` — single :meth:`LLMProvider.chat` request.

A thin wrapper around :meth:`LLMProvider.chat` that takes a single
prompt string, frames it as a one-shot user message, and returns the
text content extracted from the provider's response. Used inside RAG
specializations where the upstream knots produce a fully-formed prompt
string and the downstream knots need a string answer.

Algorithm:
    1. Validate ``llm``, ``max_tokens``, ``temperature``, and ``prompt``
       types; raise ``TypeError`` / ``ValueError`` on bad inputs.
    2. Optionally prepend a system message when ``system`` is non-empty.
    3. Append a user message containing ``prompt``.
    4. Call ``llm.chat(messages, **chat_kwargs)`` forwarding
       ``max_tokens`` and ``temperature`` only when provided, reporting the
       outcome through
       :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
       (ADR agents-speaks-core WS4a/WS5b).
    5. Extract and return the text content from the raw response via
       ``_extract_text``.

References:
    - pirn-native implementation; no external algorithm reference.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.observability.agent_call_recorder import AgentCallRecorder


class LLMChatCall(Knot):
    """Calls :meth:`LLMProvider.chat` and returns the assistant text."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        system: Knot | str | None = None,
        max_tokens: Knot | int | None = None,
        temperature: Knot | float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt,
            llm=llm,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **_: Any,
    ) -> str:
        """Send the prompt as a user message to the LLM and return the extracted text response.

        Args:
            prompt: The fully-formed prompt string to send as a user message.

        Returns:
            The extracted text content from the LLM response.

        Raises:
            ValueError: If max_tokens is not a positive int or temperature is not a number.
        """
        if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
            raise ValueError(
                f"LLMChatCall: max_tokens must be a positive int or None, got {max_tokens!r}"
            )
        if temperature is not None and not isinstance(temperature, (int, float)):
            raise ValueError(
                f"LLMChatCall: temperature must be a number or None, got {temperature!r}"
            )
        actual_temperature = float(temperature) if temperature is not None else None
        chat_messages: list[dict[str, Any]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.append({"role": "user", "content": prompt})
        chat_kwargs: dict[str, Any] = {}
        if max_tokens is not None:
            chat_kwargs["max_tokens"] = max_tokens
        if actual_temperature is not None:
            chat_kwargs["temperature"] = actual_temperature
        start = time.perf_counter()
        try:
            response = await llm.chat(chat_messages, **chat_kwargs)
        except Exception as exc:
            await AgentCallRecorder.record(
                knot_id=self.knot_id,
                kind="llm",
                ok=False,
                latency=time.perf_counter() - start,
                detail=str(exc),
            )
            raise
        await AgentCallRecorder.record(
            knot_id=self.knot_id,
            kind="llm",
            ok=True,
            latency=time.perf_counter() - start,
        )
        return self._extract_text(response)

    @staticmethod
    def _extract_text(raw: Mapping[str, Any] | str) -> str:
        match raw:
            case str():
                return raw
            case {"content": str() as content}:
                return content
            case {"content": [{"text": str() as text}, *_]}:
                return text
            case {"content": [str() as first, *_]}:
                return first
            case {"text": str() as text}:
                return text
            case _:
                return str(raw)
