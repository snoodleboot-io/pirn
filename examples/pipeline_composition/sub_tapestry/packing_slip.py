"""``PackingSlip`` — the slip produced by the inner packing step.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PackingSlip:
    order_id: str
    items: list[str]
    weight_kg: float
