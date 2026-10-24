"""``ClaimSupport`` — the evidence a memory-store search found for one claim.

``ClaimVerification`` used to return a bare ``bool``, which is core's ``Check``
role without a ``Gate(check=)`` wiring (PIR-874). It is a read, not a gate, so
it returns the evidence instead: ``data`` is the hits the search returned and
``metadata`` is the :class:`ClaimSupportFrame` verdict, so a downstream knot can
cite the hits rather than receive a single bit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.guardrails.claim_support_frame import ClaimSupportFrame


class ClaimSupport(AgentResult[ClaimSupportFrame, tuple[Mapping[str, Any], ...]]):
    """Hits found for one claim, plus the supported/unsupported verdict.

    ``ClaimSupport`` is ``Payload[ClaimSupportFrame, tuple[Mapping[str, Any], ...]]``
    (PIR-874). Read the verdict as ``metadata.supported`` and the evidence as
    ``data``.
    """

    def __init__(self, claim: str, hits: Sequence[Mapping[str, Any]]) -> None:
        """Build the result from the claim and the hits its search returned.

        Args:
            claim: The claim that was searched for.
            hits: The hits the store returned; ``supported`` and ``hit_count``
                are derived from them.
        """
        evidence = tuple(hits)
        frame = ClaimSupportFrame(claim=claim, supported=bool(evidence), hit_count=len(evidence))
        super().__init__(metadata=frame, data=evidence)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Audit the frame plus the hit count; never the retrieved documents."""
        audit = dict(super()._pirn_audit_dict())
        audit["hit_count"] = len(self.data)
        return audit
