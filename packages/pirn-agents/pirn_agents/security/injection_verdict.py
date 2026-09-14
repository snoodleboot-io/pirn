"""``InjectionVerdict`` — the outcome of screening content for prompt injection.

A frozen value carrying whether the content was ``flagged``, a ``score`` in
``[0, 1]``, the ``decided_by`` stage (``"heuristic"``, ``"llm"``, or ``"clean"``),
a human-readable ``reason``, and the tuple of ``matched`` heuristic snippets.
Returned by :class:`~pirn_agents.security.injection_screen.InjectionScreen` so a
caller can decide whether to block, quarantine, or pass the content through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class InjectionVerdict(PirnOpaqueValue):
    """Immutable result of an injection screen.

    Attributes
    ----------
    flagged:
        ``True`` when the content is judged an injection attempt.
    score:
        Suspicion score in ``[0.0, 1.0]``.
    decided_by:
        The stage that produced the verdict: ``"clean"``, ``"heuristic"``, or
        ``"llm"``.
    reason:
        Human-readable explanation for logging / audit.
    matched:
        The heuristic snippets that matched, if any.
    """

    flagged: bool
    score: float
    decided_by: str
    reason: str
    matched: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the field types and the ``score`` domain.

        Raises
        ------
        TypeError
            If ``flagged`` is not a bool, ``score`` is not a real number, or
            ``decided_by`` / ``reason`` are not strings.
        ValueError
            If ``score`` falls outside ``[0, 1]`` or ``decided_by`` is unknown.
        """
        if not isinstance(self.flagged, bool):
            raise TypeError("InjectionVerdict: flagged must be a bool")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError("InjectionVerdict: score must be a real number")
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError(f"InjectionVerdict: score must be in [0, 1], got {self.score!r}")
        if self.decided_by not in ("clean", "heuristic", "llm"):
            raise ValueError(
                f"InjectionVerdict: decided_by must be 'clean'|'heuristic'|'llm', "
                f"got {self.decided_by!r}"
            )
        if not isinstance(self.reason, str):
            raise TypeError("InjectionVerdict: reason must be a str")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the verdict."""
        return {
            "flagged": self.flagged,
            "score": float(self.score),
            "decided_by": self.decided_by,
            "reason": self.reason,
            "matched": list(self.matched),
        }
