"""Example: Order processing pipeline with SubTapestry nodes.

Demonstrates how SubTapestry lets each major stage of a pipeline own a
complete inner execution graph.  The outer tapestry stays clean — three
high-level nodes — while each inner pipeline is independently versioned,
cached, and visualised.

# YAML usage note:
# SubTapestry subclasses can be referenced from YAML pipelines as
#     type: knot
#     callable: examples.pipeline_composition.sub_tapestry.validate_order.ValidateOrder
# The outer pipeline topology goes in YAML; the inner pipeline logic
# stays in process() in Python.

Topology:

    order ──► ValidateOrder ──► FulfillOrder ──► notify_customer
                 (inner: inventory + payment)
                                 (inner: pack + ship)

Run with:
    uv run python -m examples.pipeline_composition.sub_tapestry
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from examples.pipeline_composition.sub_tapestry.fulfill_order import FulfillOrder
from examples.pipeline_composition.sub_tapestry.knots import notify_customer
from examples.pipeline_composition.sub_tapestry.order import Order
from examples.pipeline_composition.sub_tapestry.validate_order import ValidateOrder


class SubTapestryExample:
    """Builds and runs the order-processing tapestry composed of SubTapestry nodes."""

    _icon: ClassVar[dict[str, str]] = {"ok": "✓", "err": "✗", "skipped": "⊘"}

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire ValidateOrder → FulfillOrder → notify_customer."""
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

    @classmethod
    def _print_run(cls, label: str, result: RunResult) -> None:
        status = "✓ succeeded" if result.succeeded else "✗ failed"
        print(f"\n── {label} ({status}) ──")
        for rec in result.lineage:
            icon = cls._icon.get(rec.outcome, "?")
            print(f"  {icon} {rec.knot_id:<12} {rec.outcome}")
        if result.exceptions:
            for exc in result.exceptions:
                print(f"    ↳ {exc.knot_id}: {exc.exc_type}: {exc.message[:80]}")

    @classmethod
    async def main(cls) -> None:
        """Run the happy path, two blocked orders, and a cached re-run."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

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
        cls._print_run("Happy path", r1)

        # 2. Payment blocked (total > $10,000)
        r2 = await t.run(RunRequest(parameters={"order": big_order, "carrier": "FastShip"}))
        cls._print_run("Blocked — payment over limit", r2)

        # 3. Unknown items
        r3 = await t.run(RunRequest(parameters={"order": unknown_order, "carrier": "SlowBoat"}))
        cls._print_run("Blocked — unknown items", r3)

        # 4. Re-run happy path — all cached
        r4 = await t.run(RunRequest(parameters={"order": happy_order, "carrier": "FastShip"}))
        cls._print_run("Re-run happy path (cached)", r4)

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
            icon = cls._icon.get(outcome, "?")
            print(f"│ {label:<32} │ {icon} {outcome:<6} │")
        print("└──────────────────────────────────┴──────────┘")
