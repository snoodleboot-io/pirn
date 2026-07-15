"""``PairwiseOutcome`` — the result of pairwise (A-vs-B) judging."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class PairwiseOutcome(PirnOpaqueValue):
    """Which of two responses the judge preferred, with bias-control context.

    Attributes
    ----------
    winner:
        ``"a"``, ``"b"``, or ``"tie"``. When position-swap is enabled and the
        two orders disagree, the outcome is forced to ``"tie"`` and
        ``consistent`` is ``False``.
    score_a:
        Fraction of (non-tie) votes ``"a"`` won across all runs, in ``[0, 1]``.
    score_b:
        Fraction of (non-tie) votes ``"b"`` won across all runs, in ``[0, 1]``.
    consistent:
        Whether the position-swapped orders agreed on the winner. Always ``True``
        when position-swap is disabled.
    detail:
        Vote tallies and per-order winners for auditing the bias controls.
    """

    winner: str
    score_a: float
    score_b: float
    consistent: bool
    detail: Mapping[str, Any] = field(default_factory=dict)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "winner": self.winner,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "consistent": self.consistent,
            "detail": dict(self.detail),
        }
