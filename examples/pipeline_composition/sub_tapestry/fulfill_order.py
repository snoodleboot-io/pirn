"""``FulfillOrder`` — SubTapestry owning the pack + ship inner pipeline.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from examples.pipeline_composition.sub_tapestry.inventory_check import InventoryCheck
from examples.pipeline_composition.sub_tapestry.knots import pack_order, ship_order
from examples.pipeline_composition.sub_tapestry.order import Order


class FulfillOrder(SubTapestry):
    """Inner pipeline: pack and ship.  Runs only after ValidateOrder succeeds."""

    async def process(
        self, order: Order, validation: InventoryCheck, carrier: str, **_: Any
    ) -> Knot:
        p_inv = Parameter(
            "inventory", InventoryCheck, default=validation, _config=KnotConfig(id="inventory")
        )
        p_order = Parameter("order", Order, default=order, _config=KnotConfig(id="order"))
        slip = pack_order(order=p_order, inventory=p_inv, _config=KnotConfig(id="pack"))
        return ship_order(slip=slip, carrier=carrier, _config=KnotConfig(id="ship"))
