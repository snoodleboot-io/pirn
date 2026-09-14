"""Unit tests for RunScopedSubscriber's registrar attribution (PIR-841)."""

from __future__ import annotations

import contextvars
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_context_vars import RunContextVars
from pirn.engine.run_scoped_subscriber import RunScopedSubscriber


def _deliver(
    subscriber: RunScopedSubscriber, knot: Knot, run_id: str | None, registrar: str | None
) -> None:
    """Call *subscriber* the way a store does: in the registering context."""
    ctx = contextvars.copy_context()
    ctx.run(RunContextVars.run_id.set, run_id)
    ctx.run(RunContextVars.dispatching_knot_id.set, registrar)
    ctx.run(subscriber, knot)


def _late() -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id="late"))


class TestRegistrarAttribution(unittest.TestCase):
    def test_records_the_dispatching_knot_as_registrar(self) -> None:
        # Arrange
        pending: list[Knot] = []
        registrars: dict[str, str] = {}
        subscriber = RunScopedSubscriber("run-a", pending, registrars)
        knot = _late()

        # Act
        _deliver(subscriber, knot, run_id="run-a", registrar="r")

        # Assert
        self.assertEqual(pending, [knot])
        self.assertEqual(registrars, {"late": "r"})

    def test_registration_outside_any_knot_records_no_registrar(self) -> None:
        # Arrange
        pending: list[Knot] = []
        registrars: dict[str, str] = {}
        subscriber = RunScopedSubscriber("run-a", pending, registrars)

        # Act
        _deliver(subscriber, _late(), run_id="run-a", registrar=None)

        # Assert
        self.assertEqual(len(pending), 1)
        self.assertEqual(registrars, {})

    def test_another_runs_registration_is_neither_queued_nor_attributed(self) -> None:
        # Arrange
        pending: list[Knot] = []
        registrars: dict[str, str] = {}
        subscriber = RunScopedSubscriber("run-a", pending, registrars)

        # Act
        _deliver(subscriber, _late(), run_id="run-b", registrar="r")

        # Assert
        self.assertEqual(pending, [])
        self.assertEqual(registrars, {})

    def test_attribution_is_optional(self) -> None:
        # Arrange
        pending: list[Knot] = []
        subscriber = RunScopedSubscriber("run-a", pending)
        knot = _late()

        # Act
        _deliver(subscriber, knot, run_id="run-a", registrar="r")

        # Assert
        self.assertEqual(pending, [knot])
