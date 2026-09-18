"""``ChainedAdmission`` validates groups at every level before taking a slot.

An inner run with bounded limits of its own is metered by a gate chained under
the enclosing run's.  A knot group the enclosing limits do not define used to
be discovered only by the parent side of the chain, *after* the own ticket was
taken -- the ticket leaked -- and only when that knot was admitted, after its
upstream knots had already run.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.concurrency.undefined_concurrency_group_error import (
    UndefinedConcurrencyGroupError,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.chained_admission import ChainedAdmission
from pirn.engine.admission.limited_admission import LimitedAdmission
from pirn.tapestry import Tapestry


def _knot(knot_id: str, group: str | None = None) -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id=knot_id, concurrency_group=group))


class _ExplodingParent(LimitedAdmission):
    """A parent gate whose admission raises something other than a refusal."""

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        raise RuntimeError("parent gate broke")


class TestChainedAdmissionHoldsNothingOnFailure(unittest.TestCase):
    def test_group_undefined_in_the_parent_raises_before_the_own_ticket_is_taken(self) -> None:
        # Arrange
        own = LimitedAdmission(ConcurrencyLimits(max_in_flight=2, groups={"api": 2}))
        parent = LimitedAdmission(ConcurrencyLimits(groups={"db": 1}))
        gate = ChainedAdmission(own=own, parent=parent)

        # Act
        with self.assertRaises(UndefinedConcurrencyGroupError):
            gate.try_admit(_knot("a", "api"))

        # Assert
        self.assertEqual(own.in_flight, 0)
        self.assertEqual(own.in_flight_in("api"), 0)
        self.assertEqual(parent.in_flight, 0)

    def test_a_raising_parent_gives_the_own_ticket_back(self) -> None:
        # Arrange
        own = LimitedAdmission(ConcurrencyLimits(max_in_flight=1))
        gate = ChainedAdmission(own=own, parent=_ExplodingParent(ConcurrencyLimits()))

        # Act
        with self.assertRaisesRegex(RuntimeError, "parent gate broke"):
            gate.try_admit(_knot("a"))

        # Assert
        self.assertEqual(own.in_flight, 0)

    def test_check_group_consults_every_level(self) -> None:
        # Arrange
        grandparent = LimitedAdmission(ConcurrencyLimits(groups={"db": 1}))
        parent = ChainedAdmission(
            own=LimitedAdmission(ConcurrencyLimits(max_in_flight=4)), parent=grandparent
        )
        gate = ChainedAdmission(
            own=LimitedAdmission(ConcurrencyLimits(groups={"api": 1})), parent=parent
        )

        # Act / Assert
        gate.check_group(_knot("ok", None))
        with self.assertRaises(UndefinedConcurrencyGroupError):
            gate.check_group(_knot("bad", "api"))


class _Counted(Knot):
    """Records the id of every execution in a class-level log the test resets."""

    executed: ClassVar[list[str]] = []

    async def process(self, **_: Any) -> int:
        _Counted.executed.append(self.knot_id)
        return 1


class _RunsAnInnerPipeline(Knot):
    """Runs an inner tapestry with bounded limits of its own under the outer run."""

    async def process(self, **_: Any) -> str:
        with Tapestry() as inner:
            first = _Counted(_config=KnotConfig(id="first"))
            _Counted(_upstream=first, _config=KnotConfig(id="grouped", concurrency_group="api"))
        await inner.run(RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})))
        return "done"


class TestCrossLevelGroupsAreValidatedAtRunStart(unittest.IsolatedAsyncioTestCase):
    async def test_inner_run_with_a_group_the_outer_limits_lack_fails_before_any_knot_runs(
        self,
    ) -> None:
        # Arrange
        _Counted.executed = []
        with Tapestry() as outer:
            _RunsAnInnerPipeline(_config=KnotConfig(id="container"))
            _Counted(_config=KnotConfig(id="db_user", concurrency_group="db"))

        # Act
        result = await outer.run(RunRequest(concurrency=ConcurrencyLimits(groups={"db": 1})))

        # Assert: the inner run was refused up front, not after "first" ran.
        self.assertFalse(result.succeeded)
        self.assertEqual(result.exceptions[0].exc_type, "UndefinedConcurrencyGroupError")
        self.assertEqual(_Counted.executed, ["db_user"])
