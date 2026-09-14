"""``SelfAskFrame`` — lineage metadata for a :class:`SelfAskResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SelfAskFrame(PirnOpaqueValue):
    """Run-level facts for a Self-Ask decomposition.

    The frame half of the ``Payload[SelfAskFrame, str]`` split (PIR-868).

    Attributes
    ----------
    subquestions:
        The sub-questions the task was decomposed into, in order.
    subanswers:
        The answer to each sub-question, aligned with ``subquestions``.
    """

    subquestions: tuple[str, ...]
    subanswers: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "subquestions": list(self.subquestions),
            "subanswers": list(self.subanswers),
        }
