"""``Order`` — the customer order flowing through the outer pipeline.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Order:
    order_id: str
    customer: str
    items: list[str]
    total: float
