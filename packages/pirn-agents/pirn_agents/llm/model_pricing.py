"""``ModelPricing`` — per-model token pricing for cost estimation.

A frozen, provider-neutral value that turns a token-usage mapping into an
estimated dollar cost. Prices are expressed per one million tokens (the unit
most public price sheets use). Cached input tokens are billed at a (usually
lower) separate rate when a provider reports them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ModelPricing(PirnOpaqueValue):
    """Per-million-token prices used to estimate the cost of a response.

    Attributes
    ----------
    input_per_million:
        Price per 1,000,000 *uncached* input tokens.
    output_per_million:
        Price per 1,000,000 output tokens.
    cached_input_per_million:
        Price per 1,000,000 cached input tokens (prompt/context cache read).
        Defaults to ``0.0``.
    """

    input_per_million: float = 0.0
    output_per_million: float = 0.0
    cached_input_per_million: float = 0.0

    def estimate_cost(self, usage: Mapping[str, int]) -> float:
        """Return the estimated cost, in the price sheet's currency.

        Reads ``input_tokens``, ``output_tokens`` and ``cached_input_tokens``
        from ``usage`` (each defaulting to ``0``). Cached tokens are billed at
        :attr:`cached_input_per_million` and deducted from the billable input
        count so they are never double-counted.

        Args:
            usage: A token-usage mapping as populated on
                :class:`pirn_agents.types.agent_response.AgentResponse`.

        Returns:
            The estimated cost as a float.
        """
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        cached = int(usage.get("cached_input_tokens", 0))
        billable_input = max(0, input_tokens - cached)
        total = (
            billable_input * self.input_per_million
            + cached * self.cached_input_per_million
            + output_tokens * self.output_per_million
        )
        return total / 1_000_000

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "input_per_million": self.input_per_million,
            "output_per_million": self.output_per_million,
            "cached_input_per_million": self.cached_input_per_million,
        }
