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
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
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
        deny_patterns: Sequence[str],
        pii_patterns: Sequence[str] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        deny_compiled: list[re.Pattern[str]] = []
        for index, raw in enumerate(deny_patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"InputGuardrailGate: deny_patterns[{index}] must be a "
                    f"string, got {type(raw).__name__}"
                )
            deny_compiled.append(re.compile(raw))
        pii_compiled: list[re.Pattern[str]] = []
        for index, raw in enumerate(pii_patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"InputGuardrailGate: pii_patterns[{index}] must be a "
                    f"string, got {type(raw).__name__}"
                )
            pii_compiled.append(re.compile(raw))
        self._deny_patterns = tuple(deny_patterns)
        self._pii_patterns = tuple(pii_patterns)
        self._deny_compiled = tuple(deny_compiled)
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        message_tuple = tuple(messages)
        for index, message in enumerate(message_tuple):
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"InputGuardrailGate: messages[{index}] must be an "
                    f"AgentMessage, got {type(message).__name__}"
                )
            for pattern in self._deny_compiled:
                if pattern.search(message.content):
                    raise ValueError(
                        f"InputGuardrailGate: messages[{index}] matched deny "
                        f"pattern {pattern.pattern!r}"
                    )
        with Tapestry() as inner:
            InputMessageScrubber(
                messages=message_tuple,
                deny_patterns=(),
                pii_patterns=self._pii_patterns,
                _config=KnotConfig(id="scrub"),
            )
        inner_result = await self._run_inner(inner)
        cleaned = inner_result.outputs.get("scrub")
        if not isinstance(cleaned, tuple):
            raise RuntimeError(
                "InputGuardrailGate: inner scrubber did not return a tuple"
            )
        return cleaned
