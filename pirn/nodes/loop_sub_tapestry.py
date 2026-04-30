"""LoopSubTapestry — an iterative SubTapestry for agentic and feedback-loop patterns.

The pattern separates into two pure functions that the framework threads together:

    step(state: S) -> tuple[Tapestry, S] | None
        Decide what to do next.  Build the inner tapestry for this iteration
        and return it alongside the updated state that ``fold`` will receive.
        Return ``None`` to terminate — the current state becomes the final result.

    fold(state: S, result: RunResult) -> S
        Integrate the iteration's outcome into state.  The returned value is
        passed to the next ``step`` call.

The framework drives the loop as a single extensible inner run.  Each
iteration is a knot inside that run, connected by edges that reflect the
sequential (or parallel) data dependencies between them.  Sub-tapestries
spawned within an iteration become child runs of the loop run.

    iteration_1 → iteration_2 → iteration_3 ...
    (all knots in one loop run, edges encode ordering and data flow)

Each iteration knot, upon completing, calls ``fold`` then ``step`` to plan the
next iteration and registers it into the running loop tapestry.  The
extensible engine picks it up in the next wave.  When ``step`` returns
``None`` a terminal sentinel knot is registered, the run drains, and the
final state is returned.

Example::

    class Refiner(LoopSubTapestry[RefinementState]):

        def step(self, state: RefinementState) -> tuple[Tapestry, RefinementState] | None:
            if state.converged or state.rounds >= MAX_ROUNDS:
                return None
            state.rounds += 1
            with Tapestry() as t:
                RefineKnot(data=state.current, _config=KnotConfig(id="refine"))
            return t, state

        def fold(self, state: RefinementState, result: RunResult) -> RefinementState:
            state.current = result.outputs["refine"]
            state.converged = _has_converged(state.current)
            return state
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import get_current_store

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry

S = TypeVar("S")

_TERMINAL_ID = "__loop_terminal__"


class _LoopTerminal(Knot):
    """Identity knot — marks loop completion and surfaces the final state."""

    async def process(self, state: Any, **_: Any) -> Any:  # type: ignore[override]
        return state


class _IterationChainKnot(SubTapestry):
    """One link in a LoopSubTapestry chain.

    Runs its pre-planned iteration tapestry, folds the result into state,
    plans the next iteration via ``step``, and self-registers the successor
    into the loop tapestry's store for the extensible engine to pick up.

    ``state`` is always the single declared input.  For iteration_1 it is a
    plain config value (the initial state).  For iteration N+1 it is the
    previous iteration knot (a Knot parent), resolved to that knot's output
    state before ``process`` is called.  The edge encodes the data dependency.
    """

    def __init__(
        self,
        *,
        _loop_sub: LoopSubTapestry,  # type: ignore[type-arg]
        _iter_tapestry: Tapestry,
        _iteration_idx: int,
        _outer_history: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_mutable_loop_sub", _loop_sub)
        object.__setattr__(self, "_mutable_iter_tapestry", _iter_tapestry)
        object.__setattr__(self, "_mutable_iteration_idx", _iteration_idx)
        # Override the history captured by SubTapestry.__init__ (which sees no
        # _CURRENT_TAPESTRY since we're constructed mid-run, not inside a
        # `with Tapestry():` block).  Explicit propagation ensures iteration
        # sub-runs are recorded to the same history store.
        if _outer_history is not None:
            object.__setattr__(self, "_mutable_outer_history", _outer_history)

    async def process(self, state: Any, **_: Any) -> Any:  # type: ignore[override]
        loop: LoopSubTapestry = object.__getattribute__(self, "_mutable_loop_sub")  # type: ignore[type-arg]
        iter_tapestry: Tapestry = object.__getattribute__(self, "_mutable_iter_tapestry")
        iteration_idx: int = object.__getattribute__(self, "_mutable_iteration_idx")
        outer_history: Any = object.__getattribute__(self, "_mutable_outer_history")

        result = await self._run_inner(iter_tapestry)
        new_state = loop.fold(state, result)

        store = get_current_store()
        if store is None:
            return new_state

        next_idx = iteration_idx + 1
        next_outcome = loop.step(new_state)
        next_knot_id = loop.step_id(new_state, next_idx)

        if next_outcome is not None:
            next_tapestry, _ = next_outcome
            next_knot = _IterationChainKnot(
                _loop_sub=loop,
                _iter_tapestry=next_tapestry,
                _iteration_idx=next_idx,
                _outer_history=outer_history,
                state=self,
                _config=KnotConfig(id=next_knot_id),
            )
            store.register(next_knot)
        else:
            store.register(_LoopTerminal(state=self, _config=KnotConfig(id=_TERMINAL_ID)))

        return new_state


class LoopSubTapestry(SubTapestry, Generic[S]):
    """Iterative SubTapestry driven by ``step`` / ``fold``.

    Subclasses implement:

    - ``step(state: S) -> tuple[Tapestry, S] | None``
    - ``fold(state: S, result: RunResult) -> S``

    All iterations execute as knots within a single extensible inner run,
    connected by edges that encode their sequential (or parallel) data
    dependencies.  Sub-tapestries spawned inside an iteration become child
    runs of the loop run.  The base class owns the iteration loop, history
    injection, and run recording.  Subclasses never call ``_run_inner``
    directly.
    """

    def step(self, state: S) -> tuple[Tapestry, S] | None:
        """Build the next iteration's graph, or return None to terminate."""
        raise NotImplementedError(f"{type(self).__name__} must implement step()")

    def fold(self, state: S, result: RunResult) -> S:
        """Integrate an iteration's result into state."""
        raise NotImplementedError(f"{type(self).__name__} must implement fold()")

    def step_id(self, state: S, idx: int) -> str:
        """Return the knot ID for the upcoming step at *idx* (1-based).

        Override to produce domain-meaningful IDs.  The default is
        ``step_{idx}``.  Called by the framework immediately before
        ``step()``, with the state as it exists at that point.
        """
        return f"step_{idx}"

    async def process(self, state: Any, **_: Any) -> Any:  # type: ignore[override]
        from pirn.tapestry import Tapestry

        first_outcome = self.step(state)
        if first_outcome is None:
            return state

        first_tapestry, first_state = first_outcome
        first_knot_id = self.step_id(first_state, 1)

        loop_t = Tapestry()

        outer_history: Any = object.__getattribute__(self, "_mutable_outer_history")

        first_knot = _IterationChainKnot(
            _loop_sub=self,
            _iter_tapestry=first_tapestry,
            _iteration_idx=1,
            _outer_history=outer_history,
            state=first_state,
            _config=KnotConfig(id=first_knot_id),
        )
        loop_t._store.register(first_knot)

        loop_result = await self._run_inner(loop_t, extensible=True)
        return loop_result.outputs[_TERMINAL_ID]
