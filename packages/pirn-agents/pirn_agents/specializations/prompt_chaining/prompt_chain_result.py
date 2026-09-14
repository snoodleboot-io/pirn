"""``PromptChainResult`` — the typed outcome of a prompt-chaining run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.prompt_chaining.prompt_chain_frame import PromptChainFrame


class PromptChainResult(AgentResult[PromptChainFrame, str]):
    """Outcome of a sequential prompt chain.

    ``PromptChainResult`` is ``Payload[PromptChainFrame, str]`` (PIR-868,
    following the ADR agents-speaks-core WS6b pattern) — ``data`` is the
    last link's output (the overall result), and ``metadata`` is the
    :class:`PromptChainFrame` carrying every link's output in order. The
    pre-ADR field names (``outputs``, ``final``) stay available as
    read-only properties, so every existing construction and
    attribute-access call site keeps compiling unchanged.
    """

    def __init__(self, outputs: tuple[str, ...], final: str) -> None:
        frame = PromptChainFrame(outputs=outputs)
        super().__init__(metadata=frame, data=final)

    @property
    def outputs(self) -> tuple[str, ...]:
        return self._metadata.outputs

    @property
    def final(self) -> str:
        return self._data

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(self._metadata._pirn_audit_dict())
        audit["final"] = self.final
        return audit
