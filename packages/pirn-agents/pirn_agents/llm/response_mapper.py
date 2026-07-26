"""``ResponseMapper`` — assembles typed responses from extracted primitives.

Extracted from ``BaseLLMProvider`` so the response-mapping responsibility lives
in one focused collaborator (SRP). It takes the provider-neutral primitives a
provider has already pulled out of its raw JSON (content text, the codec's
tool-message object, finish reason, token usage) and folds them into an
:class:`~pirn_agents.types.messaging.agent_response.AgentResponse`: decoding native tool
calls through the injected :class:`~pirn_agents.tools.tool_call_codec.ToolCallCodec`
and estimating cost from the optional
:class:`~pirn_agents.llm.model_pricing.ModelPricing`. It also renders an
``AgentResponse`` back into a plain mapping for the ``dict``-returning chat API.

Vendor-specific extraction stays behind the provider's own parsing hooks; this
mapper names no vendor and touches no wire shapes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.types.messaging.agent_response import AgentResponse


class ResponseMapper:
    """Builds :class:`AgentResponse`s (and plain mappings) from primitives."""

    def __init__(self, *, codec: ToolCallCodec, pricing: ModelPricing | None) -> None:
        """Initialise with the tool-call codec and optional price sheet.

        Args:
            codec: Codec decoding a provider tool-message into neutral
                :class:`~pirn_agents.tools.tool_call.ToolCall`s.
            pricing: Optional per-model price sheet; ``None`` disables cost
                estimation (``cost`` is then ``None``).
        """
        self._codec: ToolCallCodec = codec
        self._pricing: ModelPricing | None = pricing

    def estimate_cost(self, usage: Mapping[str, int]) -> float | None:
        """Return the estimated cost for ``usage``, or ``None`` without pricing."""
        return self._pricing.estimate_cost(usage) if self._pricing is not None else None

    def to_agent_response(
        self,
        *,
        content: str,
        tool_message: Any,
        finish_reason: str,
        usage: dict[str, int],
    ) -> AgentResponse:
        """Fold extracted primitives into an :class:`AgentResponse`.

        Args:
            content: The assistant's textual reply.
            tool_message: The object the codec decodes native tool calls from.
            finish_reason: The neutral finish reason.
            usage: The neutral token-usage mapping (also drives cost).
        """
        return AgentResponse(
            content=content,
            tool_calls=tuple(self._codec.decode_calls(tool_message)),
            finish_reason=finish_reason,
            usage=usage,
            cost=self.estimate_cost(usage),
        )

    @staticmethod
    def to_mapping(response: AgentResponse) -> dict[str, Any]:
        """Render an :class:`AgentResponse` as a plain mapping."""
        return {
            "content": response.content,
            "tool_calls": [dict(call.arguments) for call in response.tool_calls],
            "finish_reason": response.finish_reason,
            "usage": dict(response.usage),
            "cost": response.cost,
        }
