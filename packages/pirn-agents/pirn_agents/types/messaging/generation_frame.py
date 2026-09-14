"""``GenerationFrame`` — lineage metadata for one model generation turn."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.types.messaging.finish_reason import FinishReason


@dataclass(frozen=True)
class GenerationFrame(PirnOpaqueValue):
    """Lineage descriptor for a single :class:`AgentResponse`.

    Carries everything about *how* a generation turn ended without carrying
    the generated text itself — the frame half of the
    ``Payload[GenerationFrame, str]`` split (ADR agents-speaks-core WS6b).

    Attributes
    ----------
    finish_reason:
        Reason the model stopped generating, from the neutral
        :class:`~pirn_agents.types.messaging.finish_reason.FinishReason`
        vocabulary — or a provider wire value the adapter did not recognise.
        Defaults to ``"stop"``.
    usage:
        Mapping of token-usage fields (e.g. ``input_tokens``,
        ``output_tokens``) returned by the provider. Defaults to an
        empty dict.
    cost:
        Estimated cost of the turn in the pricing sheet's currency, or
        ``None`` when no pricing was configured.
    tool_calls:
        Tuple of :class:`~pirn_agents.tools.tool_call.ToolCall`s the agent
        wants dispatched before producing a final answer. Empty when the
        agent has nothing to defer.
    model:
        The provider-reported model identity that produced the turn, or
        ``None`` when the connector did not report one.
    provider:
        The provider identity (e.g. ``"anthropic"``, ``"openai"``) that
        produced the turn, or ``None`` when not reported.
    """

    finish_reason: str = FinishReason.STOP.value
    usage: Mapping[str, int] = field(default_factory=dict[str, int])
    cost: float | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    model: str | None = None
    provider: str | None = None

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "cost": self.cost,
            "tool_calls": self._audit_all(self.tool_calls),
            "model": self.model,
            "provider": self.provider,
        }
