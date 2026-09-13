"""Engine._absorb_pending must not lose a registration that races the drain.

Under ``ThreadDispatcher`` a knot on a worker thread can register a newcomer
while the engine loop is draining ``pending_new``.  The drain used to copy
the list and then clear it, so a registration landing between the two was
dropped (PIR-841).
"""

from __future__ import annotations

import unittest
from collections.abc import Iterator
from typing import Any, SupportsIndex, overload

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_context import RunContext
from pirn.engine.engine import Engine
from pirn.engine.scheduling.dependency_tracker import DependencyTracker
from pirn.engine.shed.shed import Shed


def _param(knot_id: str) -> Parameter:
    return Parameter(knot_id, int, default=1, _config=KnotConfig(id=knot_id))


class _RacingPending(list[Knot]):
    """A ``pending_new`` that receives one more registration mid-snapshot.

    The extra knot is appended the first time the engine reads the list's
    contents, which is exactly where a worker thread's ``append`` can land.
    """

    def __init__(self, first: Knot, racer: Knot) -> None:
        super().__init__([first])
        self._racer: Knot | None = racer

    def _race(self) -> None:
        if self._racer is not None:
            racer, self._racer = self._racer, None
            super().append(racer)

    def __iter__(self) -> Iterator[Knot]:
        items = list(super().__iter__())
        self._race()
        return iter(items)

    @overload
    def __getitem__(self, index: SupportsIndex) -> Knot: ...

    @overload
    def __getitem__(self, index: slice) -> list[Knot]: ...

    def __getitem__(self, index: Any) -> Any:
        items = super().__getitem__(index)
        self._race()
        return items


class TestAbsorbPendingDrain(unittest.TestCase):
    def test_a_registration_landing_during_the_drain_is_kept(self) -> None:
        # Arrange
        root = _param("root")
        shed = Shed.from_terminals([root])
        tracker = DependencyTracker(shed)
        ctx = RunContext(run_id="run-a", terminals_requested=["root"], dispatcher_name="test")
        first, racer = _param("first"), _param("racer")
        pending = _RacingPending(first, racer)

        # Act
        ready = Engine()._absorb_pending(shed, pending, {}, {}, ctx, tracker)

        # Assert: `first` was merged, and `racer` is still queued for the
        # next drain rather than silently discarded.
        self.assertEqual(ready, ["first"])
        self.assertEqual(list.__iter__(pending).__next__(), racer)
        self.assertEqual(len(pending), 1)
