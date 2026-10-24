"""Guard: nothing in ``pirn_agents`` configures another object by writing its privates.

ADR "agents speaks core" (2026-09-13), WS0b. Core forwards the enclosing run's
execution plane — dispatcher, admission gate and limits, admission observers,
replay posture, identity resolver — into every inner run, and
``SubTapestry._run_inner`` / the ``_inner_*`` hooks are the sanctioned way to
override it. Reaching into ``tapestry._dispatcher`` / ``tapestry._concurrency``
from downstream code is a shadow of that seam.

There is no allowlist and no field list. The version this replaced froze an
(empty) inventory of findings against a pinned set of eleven ``Tapestry`` field
names — a gate that can only ever see the fields someone remembered to write
down. The assertion below is the rule itself: **no scope assigns a private
attribute of an object that is not its own**, whatever the attribute or the
receiver. :class:`TestReachThroughDetectorFires` proves the detector fires, so
an empty finding means an empty tree and not a blind detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.core_seams.execution_plane_reach_through_inventory import (
    ExecutionPlaneReachThroughInventory,
)


class TestNothingReachesThroughToPrivateState(unittest.TestCase):
    """Every object configures itself. Asserted, not inventoried."""

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.modules()) >= 500, len(AgentsSourceIndex.modules())

    def test_no_scope_assigns_another_objects_private_attribute(self) -> None:
        found = ExecutionPlaneReachThroughInventory.discover()
        assert found == {}, {label: sorted(writes) for label, writes in found.items()}


class TestReachThroughDetectorFires(unittest.TestCase):
    """The detector fires on the shape it names, and not on an object's own state."""

    @staticmethod
    def _scopes(source: str) -> dict[str, frozenset[str]]:
        return ExecutionPlaneReachThroughInventory.reach_throughs_in(ast.parse(source))

    def test_rule_fires_on_assigning_a_tapestrys_private_concurrency(self) -> None:
        found = self._scopes(
            "class MapAgent(SubTapestry):\n"
            "    def _apply_run_settings(self, tapestry, *, live_items):\n"
            "        tapestry._concurrency = ConcurrencyLimits(groups={'g': 4})\n"
        )
        assert found == {"MapAgent": frozenset({"tapestry._concurrency"})}

    def test_rule_fires_on_a_field_no_pinned_list_would_have_named(self) -> None:
        """The failure mode of the version this replaced: an unlisted field."""
        found = self._scopes(
            "class Runner(SubTapestry):\n"
            "    def _apply(self, tapestry):\n"
            "        tapestry._replay_budget = 3\n"
        )
        assert found == {"Runner": frozenset({"tapestry._replay_budget"})}

    def test_rule_fires_on_a_receiver_that_is_not_a_tapestry(self) -> None:
        found = self._scopes("def wire(gate):\n    gate._limit = 4\n")
        assert found == {"<module>": frozenset({"gate._limit"})}

    def test_rule_fires_on_augmented_assignment_and_deletion(self) -> None:
        found = self._scopes(
            "class Meddler:\n"
            "    def bump(self, other):\n"
            "        other._count += 1\n"
            "    def clear(self, other):\n"
            "        del other._cache\n"
        )
        assert found == {"Meddler": frozenset({"other._count", "other._cache"})}

    def test_rule_ignores_a_class_setting_its_own_state(self) -> None:
        found = self._scopes(
            "class DataStoreMemoryStore:\n"
            "    def __init__(self, data_store):\n"
            "        self._data_store = data_store\n"
            "        self._history = []\n"
        )
        assert found == {}

    def test_rule_ignores_writing_to_a_copy_of_self(self) -> None:
        """A clone of ``self`` is still ``self``'s own state."""
        found = self._scopes(
            "class ToolFactory:\n"
            "    def with_name(self, name):\n"
            "        clone = copy.copy(self)\n"
            "        clone._name = name\n"
            "        return clone\n"
        )
        assert found == {}

    def test_rule_ignores_the_sanctioned_override(self) -> None:
        found = self._scopes(
            "class MapAgent(SubTapestry):\n"
            "    def _inner_concurrency(self):\n"
            "        return ConcurrencyLimits(groups={'g': self._cap})\n"
            "    async def _run_inner(self, tapestry, **kw):\n"
            "        return await super()._run_inner(tapestry, dispatcher=self._dispatcher)\n"
        )
        assert found == {}

    def test_rule_ignores_reading_another_objects_private_attribute(self) -> None:
        """Reading is coupling; *assigning* is configuring, which is the seam's business."""
        found = self._scopes("def pick(inner):\n    return inner._history\n")
        assert found == {}

    def test_rule_ignores_a_public_attribute_write(self) -> None:
        found = self._scopes("def wire(gate):\n    gate.limit = 4\n")
        assert found == {}
