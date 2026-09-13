"""Ratchet: freeze the ``pirn_agents`` sites that configure an inner run by
writing a ``Tapestry``'s private execution fields.

ADR "agents speaks core" (2026-09-13), WS0b.  Core now forwards the enclosing
run's execution plane — dispatcher, admission gate and limits, admission
observers, replay posture, identity resolver — into every inner run, and
``SubTapestry._run_inner`` / the ``_inner_*`` hooks are the sanctioned way to
override it.  Reaching into ``tapestry._dispatcher`` / ``tapestry._concurrency``
/ ``tapestry._admission_observers`` from downstream code is therefore a
shadow of that seam, and this ratchet keeps the count from growing.

The allowlist is asserted by **exact equality**, deliberately:

* adding a reach-through fails, because the finding is not in the list;
* removing one *without* updating the list also fails, because the list still
  names it.

The inventory is empty on ``main`` today: the one known site
(``batch/map_agent.py::MapAgent._apply_run_settings`` on the WS4b branch)
predates the seam and must be replaced by ``_run_inner(dispatcher=,
concurrency=, admission_observers=)`` when that branch rebases — this test is
what tells it so.
"""

from __future__ import annotations

import ast
import unittest

from tests.core_seams.execution_plane_reach_through_inventory import (
    ExecutionPlaneReachThroughInventory,
)

# --- known reach-throughs, frozen (ADR agents-speaks-core, WS0b) ------------

EXECUTION_PLANE_REACH_THROUGHS: frozenset[str] = frozenset()


class TestExecutionPlaneReachThroughsAreFrozen(unittest.TestCase):
    """Freeze the reach-through inventory.  Exact equality in both directions."""

    def test_reach_throughs_are_frozen(self) -> None:
        found = ExecutionPlaneReachThroughInventory.discover()
        assert found == EXECUTION_PLANE_REACH_THROUGHS, {
            "new reach-throughs": sorted(found - EXECUTION_PLANE_REACH_THROUGHS),
            "fixed — remove from EXECUTION_PLANE_REACH_THROUGHS": sorted(
                EXECUTION_PLANE_REACH_THROUGHS - found
            ),
        }


class TestReachThroughDetectorIsDiscriminating(unittest.TestCase):
    """The detector must fire on the shapes it names, and not on clean code.

    An empty frozen inventory passes for the wrong reason if the detector is
    blind, so every shape it is meant to catch is pinned here against the
    exact source WS4b's ``MapAgent._apply_run_settings`` used.
    """

    @staticmethod
    def _scopes_with_reach_through(source: str) -> set[str]:
        return ExecutionPlaneReachThroughInventory.reach_throughs_in(ast.parse(source))

    def test_assigning_a_tapestry_s_private_concurrency_is_a_reach_through(self) -> None:
        source = (
            "class MapAgent(SubTapestry):\n"
            "    def _apply_run_settings(self, tapestry, *, live_items):\n"
            "        tapestry._concurrency = ConcurrencyLimits(groups={'g': 4})\n"
        )
        assert self._scopes_with_reach_through(source) == {"MapAgent"}

    def test_assigning_a_private_dispatcher_and_observers_is_a_reach_through(self) -> None:
        source = (
            "class MapAgent(SubTapestry):\n"
            "    def _apply_run_settings(self, tapestry):\n"
            "        tapestry._dispatcher = self._mutable_dispatcher\n"
            "        tapestry._admission_observers = self._observers_for_run()\n"
        )
        assert self._scopes_with_reach_through(source) == {"MapAgent"}

    def test_reading_a_private_field_of_another_object_is_a_reach_through(self) -> None:
        source = "def pick(inner):\n    return inner._history\n"
        assert self._scopes_with_reach_through(source) == {"<module>"}

    def test_a_class_touching_its_own_private_state_is_not_a_reach_through(self) -> None:
        source = (
            "class DataStoreMemoryStore:\n"
            "    def __init__(self, data_store):\n"
            "        self._data_store = data_store\n"
            "        self._history = []\n"
        )
        assert self._scopes_with_reach_through(source) == set()

    def test_the_sanctioned_override_is_not_a_reach_through(self) -> None:
        source = (
            "class MapAgent(SubTapestry):\n"
            "    def _inner_concurrency(self):\n"
            "        return ConcurrencyLimits(groups={'g': self._mutable_concurrency})\n"
            "    async def _run_inner(self, tapestry, **kw):\n"
            "        return await super()._run_inner(tapestry, dispatcher=self._mutable_dispatcher)\n"
        )
        assert self._scopes_with_reach_through(source) == set()

    def test_a_public_property_read_is_not_a_reach_through(self) -> None:
        source = "def pick(inner):\n    return inner.dispatcher, inner.concurrency\n"
        assert self._scopes_with_reach_through(source) == set()
