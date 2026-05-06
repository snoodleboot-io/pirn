"""``InputGuardrailGate`` — pre-prompt safety gate.

A :class:`SubTapestry` wrapping :class:`InputMessageScrubber`. Scans
incoming :class:`AgentMessage`s for prompt-injection deny patterns
(raises :class:`ValueError` on a match) and redacts PII matches.
Returns the cleaned tuple of messages so downstream knots can wire
straight onto the gate's output.

Deny-pattern checking runs synchronously *before* the inner tapestry
spins up so a :class:`ValueError` propagates straight out of the
SubTapestry's ``process`` without being wrapped in
:class:`SubTapestryError` — the inner pipeline only handles the PII
redaction stage.

Algorithm:
    1. Compile each deny pattern string using :func:`compile_safe_pattern`;
       raise :class:`ValueError` on invalid regex.
    2. Iterate over ``messages`` in order:
       a. Raise :class:`TypeError` if an element is not an :class:`AgentMessage`.
       b. Raise :class:`ValueError` immediately if any compiled deny pattern
          matches the message content.
    3. Run an inner :class:`Tapestry` containing a single
       :class:`InputMessageScrubber` with ``deny_patterns=()`` and
       ``pii_patterns`` forwarded from the caller.
    4. Return the cleaned tuple of :class:`AgentMessage` instances produced
       by the inner scrubber.


References:
    - pirn-native: :class:`pirn.domains.agents.specializations.guardrails.input_message_scrubber.InputMessageScrubber`
    - pirn-native: :class:`pirn.domains.agents.types.agent_message.AgentMessage`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents._regex_utils import compile_safe_pattern
from pirn.domains.agents.specializations.guardrails.input_message_scrubber import (
    InputMessageScrubber,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class InputGuardrailGate(SubTapestry):
    """Pre-prompt deny + PII redaction gate over agent messages."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        deny_patterns: Knot | Sequence[str],
        pii_patterns: Knot | Sequence[str] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            deny_patterns=deny_patterns,
            pii_patterns=pii_patterns,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        deny_patterns: Sequence[str] = (),
        pii_patterns: Sequence[str] = (),
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Reject messages matching deny patterns and redact PII, returning the cleaned message tuple.

        Args:
            messages: The sequence of agent messages to validate and scrub.

        Returns:
            A tuple of cleaned AgentMessage instances with PII redacted.

        Raises:
            TypeError: If any element of messages is not an AgentMessage.
            ValueError: If any message content matches a deny pattern.
        """
        deny_compiled = [
            compile_safe_pattern(raw, index=i, owner="InputGuardrailGate", field="deny_patterns")
            for i, raw in enumerate(deny_patterns)
        ]
        message_tuple = tuple(messages)
        for index, message in enumerate(message_tuple):
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"InputGuardrailGate: messages[{index}] must be an "
                    f"AgentMessage, got {type(message).__name__}"
                )
            for pattern in deny_compiled:
                if pattern.search(message.content):
                    raise ValueError(
                        f"InputGuardrailGate: messages[{index}] matched deny "
                        f"pattern {pattern.pattern!r}"
                    )
        with Tapestry() as inner:
            InputMessageScrubber(
                messages=message_tuple,
                deny_patterns=(),
                pii_patterns=tuple(pii_patterns),
                _config=KnotConfig(id="scrub"),
            )
        inner_result = await self._run_inner(inner)
        cleaned = inner_result.outputs.get("scrub")
        if not isinstance(cleaned, tuple):
            raise RuntimeError("InputGuardrailGate: inner scrubber did not return a tuple")
        return cleaned
