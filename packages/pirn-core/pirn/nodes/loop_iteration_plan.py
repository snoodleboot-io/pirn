"""``LoopIterationPlan`` — the non-graph half of one ``LoopSubTapestry`` iteration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pirn.core.pirn_opaque_value import PirnOpaqueValue

if TYPE_CHECKING:
    from pirn.backends.base.run_history import RunHistory
    from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
    from pirn.tapestry import Tapestry

#: The loop state type, shared with the ``LoopSubTapestry`` the plan belongs to.
S = TypeVar("S")


class LoopIterationPlan(PirnOpaqueValue, Generic[S]):
    """What one iteration of a loop needs that cannot travel the knot graph.

    An ``IterationChainKnot`` needs four things besides its ``state``: the
    ``LoopSubTapestry`` whose ``fold``/``step`` it calls, the ``Tapestry`` that
    iteration's graph was planned into, which iteration it is, and the history
    the loop's inner runs are recorded in.  They used to be four constructor
    keywords the knot stashed on ``_mutable_`` slots and read back off ``self``
    in ``process()`` -- inputs hidden as state, so ``process()`` could not be
    called standalone with plain values (Rule 2) and none of them was validated
    or recorded (PIR-873).

    None of the four can be a declared input on its own.  The loop *is* a
    ``Knot``, so passing it by keyword would wire the container as a parent of a
    knot inside its own inner tapestry -- an edge to a knot that graph does not
    contain.  A ``Tapestry`` and a ``RunHistory`` have no pydantic schema, so
    neither can be a validated config value.  Wrapping all four in one
    ``PirnOpaqueValue`` makes them a single declared input the framework
    validates by ``isinstance`` and records as an identity token, which is what
    that mixin exists for: a live resource wired into a knot, checked at the
    boundary and never descended into.

    Attributes:
        loop: The ``LoopSubTapestry`` this iteration belongs to.
        tapestry: The tapestry holding this iteration's planned graph.
        index: 1-based iteration number.
        history: The history the loop's inner runs are recorded in, or ``None``
            to read the enclosing run's from the context.
    """

    def __init__(
        self,
        *,
        loop: LoopSubTapestry[S],
        tapestry: Tapestry,
        index: int,
        history: RunHistory | None = None,
    ) -> None:
        """Bind one iteration's non-graph context.

        Args:
            loop: The ``LoopSubTapestry`` whose ``fold``/``step`` this iteration calls.
            tapestry: The tapestry this iteration's graph was planned into.
            index: 1-based iteration number.
            history: The history the loop's inner runs are recorded in.
        """
        self._loop = loop
        self._tapestry = tapestry
        self._index = index
        self._history = history

    @property
    def loop(self) -> LoopSubTapestry[S]:
        """The ``LoopSubTapestry`` this iteration belongs to."""
        return self._loop

    @property
    def tapestry(self) -> Tapestry:
        """The tapestry holding this iteration's planned graph."""
        return self._tapestry

    @property
    def index(self) -> int:
        """1-based iteration number."""
        return self._index

    @property
    def history(self) -> RunHistory | None:
        """The history the loop's inner runs are recorded in, if one was captured."""
        return self._history

    def next_plan(self, *, tapestry: Tapestry, history: RunHistory | None) -> LoopIterationPlan[S]:
        """Return the plan for the iteration after this one.

        Args:
            tapestry: The next iteration's planned graph.
            history: The history to record its inner run in.

        Returns:
            A plan for the same loop at ``index + 1``.
        """
        return LoopIterationPlan(
            loop=self._loop, tapestry=tapestry, index=self._index + 1, history=history
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """What lineage records for this plan: the loop and which iteration it is."""
        return {
            "loop": type(self._loop).__qualname__,
            "loop_knot_id": self._loop.knot_id,
            "index": self._index,
        }
