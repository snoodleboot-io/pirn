"""``ValidateOrder`` — SubTapestry owning the inventory + payment inner pipeline.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from examples.pipeline_composition.sub_tapestry.knots import authorize_payment, check_inventory
from examples.pipeline_composition.sub_tapestry.order import Order


class ValidateOrder(SubTapestry):
    """Inner pipeline: inventory check + payment auth, both must succeed."""

    async def process(self, order: Order, **_: Any) -> Knot:
        p = Parameter("order", Order, default=order, _config=KnotConfig(id="order"))
        authorize_payment(order=p, _config=KnotConfig(id="payment"))
        return check_inventory(order=p, _config=KnotConfig(id="inventory"))
