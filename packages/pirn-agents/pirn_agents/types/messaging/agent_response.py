"""The final (or intermediate) response surfaced by an agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.payload import Payload

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.types.messaging.finish_reason import FinishReason
from pirn_agents.types.messaging.generation_frame import GenerationFrame


class AgentResponse(Payload[GenerationFrame, str]):
    """Outcome of one agent turn: a :class:`GenerationFrame` plus the reply text.

    ``AgentResponse`` is ``Payload[GenerationFrame, str]`` (ADR
    agents-speaks-core WS6b) — ``data`` is the free-form textual reply,
    ``metadata`` is the :class:`~pirn_agents.types.messaging.generation_frame.GenerationFrame`
    describing how the turn ended. The pre-ADR field names
    (``content``, ``tool_calls``, ``finish_reason``, ``usage``, ``cost``) stay
    available as read-only properties, so every existing construction and
    attribute-access call site keeps compiling unchanged; only code that
    pattern-matched on ``dataclasses.fields`` or called
    ``dataclasses.replace`` (neither occurs in this codebase) would need to
    change to :meth:`derive`.

    Attributes
    ----------
    content:
        Free-form textual reply (the payload's ``data``).
    tool_calls:
        Tuple of :class:`ToolCall`s the agent wants to dispatch before
        producing a final answer. Empty when the agent has nothing to
        defer.
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
        ``None`` when no pricing was configured. Populated by LLM provider
        connectors from :attr:`usage` and a per-model price sheet.
    model:
        The provider-reported model identity that produced the turn, or
        ``None`` when the connector did not report one.
    provider:
        The provider identity (e.g. ``"anthropic"``, ``"openai"``) that
        produced the turn, or ``None`` when not reported.
    """

    def __init__(
        self,
        content: str,
        *,
        tool_calls: tuple[ToolCall, ...] = (),
        finish_reason: str = FinishReason.STOP.value,
        usage: Mapping[str, int] | None = None,
        cost: float | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        frame = GenerationFrame(
            finish_reason=finish_reason,
            usage=dict(usage or {}),
            cost=cost,
            tool_calls=tuple(tool_calls),
            model=model,
            provider=provider,
        )
        super().__init__(metadata=frame, data=content)

    @property
    def frame(self) -> GenerationFrame:
        return self._metadata

    @property
    def content(self) -> str:
        return self._data

    @property
    def tool_calls(self) -> tuple[ToolCall, ...]:
        return self._metadata.tool_calls

    @property
    def finish_reason(self) -> str:
        return self._metadata.finish_reason

    @property
    def usage(self) -> Mapping[str, int]:
        return self._metadata.usage

    @property
    def cost(self) -> float | None:
        return self._metadata.cost

    @property
    def model(self) -> str | None:
        return self._metadata.model

    @property
    def provider(self) -> str | None:
        return self._metadata.provider

    def derive(self, content: str, **frame_overrides: Any) -> AgentResponse:
        """Build a new :class:`AgentResponse` derived from this one.

        Inherits every :class:`GenerationFrame` field from this response
        (``tool_calls``, ``finish_reason``, ``usage``, ``cost``, ``model``,
        ``provider``) and pairs them with the new ``content``. Any frame
        field may be overridden via ``frame_overrides`` — e.g. a
        post-processing knot that strips tool calls after dispatching them:
        ``response.derive(cleaned_text, tool_calls=())``.

        Args:
            content: The new reply text to carry in the derived response.
            **frame_overrides: Overrides for any :class:`GenerationFrame`
                field.

        Returns:
            A new ``AgentResponse`` with the derived frame and ``content``.
        """
        fields: dict[str, Any] = {
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "cost": self.cost,
            "model": self.model,
            "provider": self.provider,
        }
        fields.update(frame_overrides)
        return AgentResponse(content=content, **fields)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["content"] = self.content
        return audit

    def __repr__(self) -> str:
        return f"{type(self).__name__}(content={self.content!r}, frame={self._metadata!r})"
