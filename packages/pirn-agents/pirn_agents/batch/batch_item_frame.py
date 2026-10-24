"""``BatchItemFrame`` — the frame half of a :class:`BatchItemResult`.

ADR agents-speaks-core WS6b splits every cross-boundary agents value into a
``Payload[Frame, Data]``; PIR-868 did so for the specialization results and
PIR-874 does so for the batch item outcome. The frame carries the item's
bookkeeping — where it sat in the input stream, its stable key, how many
attempts it took and how long it ran — while the data half is the item's core
``Result`` (see :mod:`pirn_agents.batch.batch_item_result`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class BatchItemFrame(PirnOpaqueValue):
    """Per-item run facts for one item of a batch.

    Attributes
    ----------
    index:
        Position of the item in the input stream (0-based). Non-negative.
    key:
        Stable identity of the item — the suffix of its knot id, and so its
        resume key in ``RunHistory``.
    attempts:
        How many times the item was attempted (1 = succeeded first try).
    latency:
        Wall-clock seconds spent on the item (queue wait excluded).
    """

    index: int
    key: str
    attempts: int = 1
    latency: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError(
                f"BatchItemResult: index must be a non-negative int, got {self.index!r}"
            )
        if not isinstance(self.key, str) or not self.key:
            raise TypeError("BatchItemResult: key must be a non-empty str")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "key": self.key,
            "attempts": self.attempts,
            "latency": self.latency,
        }
