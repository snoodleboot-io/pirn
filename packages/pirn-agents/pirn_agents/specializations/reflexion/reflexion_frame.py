"""``ReflexionFrame`` — lineage metadata for a :class:`ReflexionResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt


@dataclass(frozen=True)
class ReflexionFrame(PirnOpaqueValue):
    """Run-level facts for a bounded Reflexion loop.

    The frame half of the ``Payload[ReflexionFrame, str]`` split (PIR-868).

    Attributes
    ----------
    succeeded:
        Whether the evaluator accepted an attempt before the iteration cap.
    iterations:
        Number of actor attempts made (1-based count).
    attempts:
        The per-attempt records, in order.
    """

    succeeded: bool
    iterations: int
    attempts: tuple[ReflexionAttempt, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        attempts: tuple[PirnOpaqueValue, ...] = self.attempts
        return {
            "succeeded": self.succeeded,
            "iterations": self.iterations,
            "attempts": [attempt._pirn_audit_dict() for attempt in attempts],
        }
