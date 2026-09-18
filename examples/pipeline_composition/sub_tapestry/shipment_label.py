"""``ShipmentLabel`` — the booked shipment returned by the inner ship step.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShipmentLabel:
    order_id: str
    tracking_number: str
    carrier: str
