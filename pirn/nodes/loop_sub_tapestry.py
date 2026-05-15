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

from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import get_current_store

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry

S = TypeVar("S")


class _LoopTerminal(Knot):
    """Identity knot — marks loop completion and surfaces the final state."""

    async def process(self, state: Any, **_: Any) -> Any:  # type: ignore[override]
        """Return the final loop state unchanged to surface loop completion.

        Args:
            state: Terminal state value produced by the last iteration chain knot.

        Returns:
            The state value unchanged, making it the observable output of the loop.
        """
        return state


class _IterationChainKnot(Knot):
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
        object.__setattr__(self, "_mutable_outer_history", _outer_history)

    async def process(self, state: Any, **_: Any) -> Any:  # type: ignore[override]
        """Run this iteration's tapestry, fold the result into state, and register the next iteration or terminal knot.

        Args:
            state: Current loop state, either the initial value or the folded output of the previous iteration.

        Returns:
            Updated state value produced by folding this iteration's RunResult.
        """
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory
        from pirn.core.run_request import RunRequest
        from pirn.tapestry import _current_history, _current_run_id

        loop: LoopSubTapestry = object.__getattribute__(self, "_mutable_loop_sub")  # type: ignore[type-arg]
        iter_tapestry: Tapestry = object.__getattribute__(self, "_mutable_iter_tapestry")
        iteration_idx: int = object.__getattribute__(self, "_mutable_iteration_idx")
        outer_history: Any = object.__getattribute__(self, "_mutable_outer_history")

        if outer_history is None:
            outer_history = _current_history.get(None)
        if outer_history is not None and not isinstance(outer_history, InMemoryHistory):
            iter_tapestry._history = outer_history

        parent_run_id = _current_run_id.get(None)
        result = await iter_tapestry.run(
            RunRequest(),
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
        )
        if not result.succeeded:
            from pirn.nodes.sub_tapestry import SubTapestryError

            raise SubTapestryError(result)

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
            store.register(
                _LoopTerminal(state=self, _config=KnotConfig(id=LoopSubTapestry._terminal_id))
            )

        return new_state


class LoopSubTapestry(SubTapestry, Generic[S]):
    """Iterative SubTapestry driven by ``step`` / ``fold``.

    Each iteration executes as a traceable knot in a single extensible inner
    run.  The loop is fully observable: every iteration appears in run history,
    with its own inputs, outputs, and timing.  Sub-tapestries spawned inside
    an iteration become child runs of the loop run.

    Subclasses implement:

    - ``step(state: S) -> tuple[Tapestry, S] | None``
    - ``fold(state: S, result: RunResult) -> S``

    The base class owns the iteration loop, history injection, and run
    recording.  Subclasses never call ``_run_inner`` directly.
    """

    _extensible_inner_run: ClassVar[bool] = True
    _terminal_id: ClassVar[str] = "__loop_terminal__"

    def _resolve_output_key(self, sink: Knot) -> str:
        return self._terminal_id

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

    async def process(self, state: Any, **_: Any) -> Knot:  # type: ignore[override]
        """Wire the iteration chain into the inner tapestry and return the sink knot.

        For a zero-iteration loop (``step`` returns ``None`` immediately),
        creates and returns a ``_LoopTerminal`` seeded with the initial state.
        For a normal loop, creates the first ``_IterationChainKnot`` — subsequent
        iterations self-register mid-run via the extensible engine.  The last
        iteration registers the ``_LoopTerminal``; ``_resolve_output_key`` always
        directs the output lookup to that terminal regardless of which knot is
        returned here.

        Args:
            state: Initial loop state passed to the first ``step`` call.

        Returns:
            The first knot registered in the inner tapestry — either a
            ``_LoopTerminal`` (zero iterations) or the first
            ``_IterationChainKnot``.
        """
        outer_history: Any = object.__getattribute__(self, "_mutable_outer_history")

        first_outcome = self.step(state)
        if first_outcome is None:
            return _LoopTerminal(
                state=state,
                _config=KnotConfig(id=self._terminal_id),
            )

        first_tapestry, first_state = first_outcome
        first_knot_id = self.step_id(first_state, 1)
        return _IterationChainKnot(
            _loop_sub=self,
            _iter_tapestry=first_tapestry,
            _iteration_idx=1,
            _outer_history=outer_history,
            state=first_state,
            _config=KnotConfig(id=first_knot_id),
        )
