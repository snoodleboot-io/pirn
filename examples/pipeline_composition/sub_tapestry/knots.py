"""Knot factories for the ``examples.pipeline_composition.sub_tapestry`` example.

``check_inventory`` and ``authorize_payment`` run inside ``ValidateOrder``,
``pack_order`` and ``ship_order`` inside ``FulfillOrder``, and
``notify_customer`` in the outer tapestry.
"""

from __future__ import annotations

from pirn.core.knot_factory import KnotFactory

from examples.pipeline_composition.sub_tapestry.inventory_check import InventoryCheck
from examples.pipeline_composition.sub_tapestry.notification import Notification
from examples.pipeline_composition.sub_tapestry.order import Order
from examples.pipeline_composition.sub_tapestry.packing_slip import PackingSlip
from examples.pipeline_composition.sub_tapestry.payment_auth import PaymentAuth
from examples.pipeline_composition.sub_tapestry.shipment_label import ShipmentLabel


@KnotFactory.knot
async def check_inventory(order: Order) -> InventoryCheck:
    """Simulates an inventory service lookup; raises if any items are missing."""
    available_catalog = {"widget", "gadget", "doohickey", "thingamajig"}
    missing = [item for item in order.items if item not in available_catalog]
    if missing:
        raise ValueError(f"items not in catalog: {missing}")
    return InventoryCheck(
        available=True,
        items_found=list(order.items),
        items_missing=[],
    )


@KnotFactory.knot
async def authorize_payment(order: Order) -> PaymentAuth:
    """Simulates a payment gateway call; raises if authorization is declined."""
    if order.total >= 10_000:
        raise ValueError(f"payment declined: amount {order.total} exceeds limit of 10,000")
    return PaymentAuth(
        authorized=True,
        auth_code=f"AUTH-{order.order_id}",
        amount=order.total,
    )


@KnotFactory.knot
async def pack_order(order: Order, inventory: InventoryCheck) -> PackingSlip:
    """Generates a packing slip from confirmed inventory."""
    weight = len(inventory.items_found) * 0.4
    return PackingSlip(
        order_id=order.order_id,
        items=inventory.items_found,
        weight_kg=round(weight, 2),
    )


@KnotFactory.knot
async def ship_order(slip: PackingSlip, carrier: str) -> ShipmentLabel:
    """Books the shipment and returns a tracking number."""
    return ShipmentLabel(
        order_id=slip.order_id,
        tracking_number=f"TRK-{slip.order_id}-001",
        carrier=carrier,
    )


@KnotFactory.knot
async def notify_customer(order: Order, fulfillment: ShipmentLabel) -> Notification:
    """Sends a dispatch notification once fulfillment is confirmed."""
    msg = (
        f"Hi {order.customer}! Your order {order.order_id} has been shipped "
        f"via {fulfillment.carrier}. Tracking: {fulfillment.tracking_number}."
    )
    return Notification(
        order_id=order.order_id,
        channel="email",
        message=msg,
        sent=True,
    )
