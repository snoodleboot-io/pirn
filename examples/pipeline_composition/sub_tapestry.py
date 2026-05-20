"""Example: Order processing pipeline with SubTapestry nodes (single-file).

Demonstrates how SubTapestry lets each major stage of a pipeline own a
complete inner execution graph.  The outer tapestry stays clean — three
high-level nodes — while each inner pipeline is independently versioned,
cached, and visualised.

# YAML usage note:
# SubTapestry subclasses can be referenced from YAML pipelines as
#     type: knot
#     callable: examples.pipeline_composition.sub_tapestry.ValidateOrder
# The outer pipeline topology goes in YAML; the inner pipeline logic
# stays in process() in Python.

Topology:

    order ──► ValidateOrder ──► FulfillOrder ──► notify_customer
                 (inner: inventory + payment)
                                 (inner: pack + ship)

Run with:
    uv run python examples/pipeline_composition/sub_tapestry.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class Order:
    order_id: str
    customer: str
    items: list[str]
    total: float


@dataclass
class InventoryCheck:
    available: bool
    items_found: list[str]
    items_missing: list[str]


@dataclass
class PaymentAuth:
    authorized: bool
    auth_code: str
    amount: float


@dataclass
class PackingSlip:
    order_id: str
    items: list[str]
    weight_kg: float


@dataclass
class ShipmentLabel:
    order_id: str
    tracking_number: str
    carrier: str


@dataclass
class Notification:
    order_id: str
    channel: str
    message: str
    sent: bool


# ----------------------------------------------------------------- inner knots (validation)


@knot
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


@knot
async def authorize_payment(order: Order) -> PaymentAuth:
    """Simulates a payment gateway call; raises if authorization is declined."""
    if order.total >= 10_000:
        raise ValueError(f"payment declined: amount {order.total} exceeds limit of 10,000")
    return PaymentAuth(
        authorized=True,
        auth_code=f"AUTH-{order.order_id}",
        amount=order.total,
    )


# ----------------------------------------------------------------- inner knots (fulfillment)


@knot
async def pack_order(order: Order, inventory: InventoryCheck) -> PackingSlip:
    """Generates a packing slip from confirmed inventory."""
    weight = len(inventory.items_found) * 0.4
    return PackingSlip(
        order_id=order.order_id,
        items=inventory.items_found,
        weight_kg=round(weight, 2),
    )


@knot
async def ship_order(slip: PackingSlip, carrier: str) -> ShipmentLabel:
    """Books the shipment and returns a tracking number."""
    return ShipmentLabel(
        order_id=slip.order_id,
        tracking_number=f"TRK-{slip.order_id}-001",
        carrier=carrier,
    )


# ----------------------------------------------------------------- SubTapestry nodes


class ValidateOrder(SubTapestry):
    """Inner pipeline: inventory check + payment auth, both must succeed."""

    async def process(self, order: Order, **_: Any) -> Knot:
        p = Parameter("order", Order, default=order, _config=KnotConfig(id="order"))
        authorize_payment(order=p, _config=KnotConfig(id="payment"))
        return check_inventory(order=p, _config=KnotConfig(id="inventory"))


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


# ----------------------------------------------------------------- outer knots


@knot
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


# ----------------------------------------------------------------- wiring


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        order = Parameter("order", Order, _config=KnotConfig(id="order"))
        carrier = Parameter("carrier", str, _config=KnotConfig(id="carrier"))

        validated = ValidateOrder(
            order=order,
            _config=KnotConfig(id="validate", validate_io=False),
        )
        fulfilled = FulfillOrder(
            order=order,
            validation=validated,
            carrier=carrier,
            _config=KnotConfig(id="fulfill", validate_io=False),
        )
        notify_customer(
            order=order,
            fulfillment=fulfilled,
            _config=KnotConfig(id="notify", validate_io=False),
        )
    return t


# ----------------------------------------------------------------- main

_ICON = {"ok": "✓", "err": "✗", "skipped": "⊘"}


def _print_run(label: str, result: RunResult) -> None:
    status = "✓ succeeded" if result.succeeded else "✗ failed"
    print(f"\n── {label} ({status}) ──")
    for rec in result.lineage:
        icon = _ICON.get(rec.outcome, "?")
        print(f"  {icon} {rec.knot_id:<12} {rec.outcome}")
    if result.exceptions:
        for exc in result.exceptions:
            print(f"    ↳ {exc.knot_id}: {exc.exc_type}: {exc.message[:80]}")


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    happy_order = Order(
        order_id="ORD-001",
        customer="Alice Smith",
        items=["widget", "gadget"],
        total=149.99,
    )
    big_order = Order(
        order_id="ORD-002",
        customer="Bob Jones",
        items=["widget"],
        total=15_000.00,
    )
    unknown_order = Order(
        order_id="ORD-003",
        customer="Carol White",
        items=["widget", "unobtainium"],
        total=99.00,
    )

    # 1. Happy path
    r1 = await t.run(RunRequest(parameters={"order": happy_order, "carrier": "FastShip"}))
    _print_run("Happy path", r1)

    # 2. Payment blocked (total > $10,000)
    r2 = await t.run(RunRequest(parameters={"order": big_order, "carrier": "FastShip"}))
    _print_run("Blocked — payment over limit", r2)

    # 3. Unknown items
    r3 = await t.run(RunRequest(parameters={"order": unknown_order, "carrier": "SlowBoat"}))
    _print_run("Blocked — unknown items", r3)

    # 4. Re-run happy path — all cached
    r4 = await t.run(RunRequest(parameters={"order": happy_order, "carrier": "FastShip"}))
    _print_run("Re-run happy path (cached)", r4)

    history.close()

    # Summary table
    print("\n┌──────────────────────────────────┬──────────┐")
    print("│ Scenario                         │ Outcome  │")
    print("├──────────────────────────────────┼──────────┤")
    scenarios = [
        ("Happy path", r1),
        ("Blocked — payment over limit", r2),
        ("Blocked — unknown items", r3),
        ("Re-run happy path (cached)", r4),
    ]
    for label, result in scenarios:
        outcome = "ok" if result.succeeded else "err"
        # cached if all non-param knots are skipped
        lineage = [rec for rec in result.lineage if rec.knot_id not in ("order", "carrier")]
        if lineage and all(rec.outcome == "skipped" for rec in lineage):
            outcome = "skipped"
        icon = _ICON.get(outcome, "?")
        print(f"│ {label:<32} │ {icon} {outcome:<6} │")
    print("└──────────────────────────────────┴──────────┘")


if __name__ == "__main__":
    asyncio.run(main())
