"""``PromptChainResult`` — the typed outcome of a prompt-chaining run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult


@dataclass(frozen=True)
class PromptChainResult(AgentResult):
    """Outcome of a sequential prompt chain.

    Attributes
    ----------
    outputs:
        The output of each link in the chain, in order.
    final:
        The last link's output (the overall result).
    """

    outputs: tuple[str, ...]
    final: str

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"outputs": list(self.outputs), "final": self.final}
