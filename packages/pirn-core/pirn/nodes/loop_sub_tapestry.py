"""LoopSubTapestry — an iterative SubTapestry for agentic and feedback-loop patterns.

The pattern separates into two pure functions that the framework threads together:

    step(state: S) -> tuple[Tapestry, S] | None
        Decide what to do next.  Build the inner tapestry for this iteration
        and return it alongside the updated state that ``fold`` will receive.
        Return ``None`` to terminate — the current state becomes the final result.

    fold(state: S, result: RunResult) -> S
        Integrate the iteration's outcome into state.  The returned value is
        passed to the next ``step`` call.

    Either may be awaitable.  Override ``astep`` / ``afold`` (``async def``)
    when planning or folding needs to await -- a backoff sleep before the
    next attempt, a budget check against a remote meter, a model call that
    decides whether to continue -- or simply declare ``step`` / ``fold`` as
    ``async def``: the framework awaits whatever they return.  The sync
    forms keep working unchanged (ADR agents-speaks-core, WS0).

        By default ``result`` is always a *successful* run — a failed iteration
        raises before ``fold`` is reached.  Set the class-level
        ``_tolerate_iteration_failures = True`` to receive failed runs too, which
        is what makes retry-until-success expressible.

The framework drives the loop as a single extensible inner run.  Each
iteration is a knot inside that run, connected by edges that reflect the
sequential (or parallel) data dependencies between them.  Sub-tapestries
spawned within an iteration become child runs of the loop run.

    iteration_1 → iteration_2 → iteration_3 ...
    (all knots in one loop run, edges encode ordering and data flow)

Each iteration knot, upon completing, calls ``fold`` then ``step`` to plan the
next iteration and registers it into the running loop tapestry.  The
extensible engine merges it when the iteration's completion is processed and
starts it at once, since its only parent has just resolved.  When ``step`` returns
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

import inspect
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes._iteration_chain_knot import _IterationChainKnot
from pirn.nodes._loop_terminal import _LoopTerminal
from pirn.nodes.sub_tapestry import SubTapestry

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry

S = TypeVar("S")


class LoopSubTapestry(SubTapestry, Generic[S]):
    """Iterative SubTapestry driven by ``step`` / ``fold``.

    Each iteration executes as a traceable knot in a single extensible inner
    run.  The loop is fully observable: every iteration appears in run history,
    with its own inputs, outputs, and timing.  Sub-tapestries spawned inside
    an iteration become child runs of the loop run.

    Emitter volume: the enclosing run's emitters are forwarded to the loop run
    *and* to each iteration's own run, so an open-ended loop delivers roughly
    one ``on_run_result`` per turn plus the status and lineage events of every
    knot inside that turn.  That is deliberate.  ``RunRetention`` (PIR-765)
    bounds history growth because ``InMemoryHistory`` is the *default* backend
    and would otherwise accumulate turns nobody opted into; there is no default
    emitter, so every emitter present belongs to an operator who asked to
    observe this pipeline, and its intake is proportional to work the loop
    actually performed.  Dropping iteration events instead would reproduce the
    defect PIR-834 fixed — work that is recorded in history and invisible to
    spans, metrics and logs — one nesting level down.  An emitter that must cap
    its own intake can filter on ``RunResult.parent_run_id`` / ``run_path``,
    which distinguish iteration runs from the loop run and from the outer run.

    Subclasses implement:

    - ``step(state: S) -> tuple[Tapestry, S] | None``
    - ``fold(state: S, result: RunResult) -> S``

    or their awaitable forms ``astep`` / ``afold``, which the framework
    calls; the defaults delegate to ``step`` / ``fold`` and await the
    result if it is awaitable, so a subclass may declare either pair, sync
    or ``async``.

    The base class owns the iteration loop, history injection, and run
    recording.  Subclasses never call ``_run_inner`` directly.

    Algorithm:
        1. Bootstrap — ``process()`` awaits ``astep(initial_state)`` to decide
           whether any iterations are needed.
        2. Zero-iteration short-circuit — if ``step`` returns ``None`` on the
           first call, a ``_LoopTerminal`` seeded with the initial state is
           registered directly in the inner tapestry and returned as the sink.
           The loop run executes that one knot and completes.
        3. First iteration — otherwise, an ``_IterationChainKnot`` for iteration
           index 1 is created with the iteration tapestry returned by ``step``
           and registered in the inner tapestry.  The initial state is wired in
           as a config value (not a parent edge) so no upstream dependency exists.
        4. Extensible inner run — ``SubTapestry.__call__`` starts the inner
           tapestry in extensible mode (``_extensible_inner_run = True``).  The
           engine executes iteration 1 and waits for more knots.
        5. Fold — when iteration N completes, ``_IterationChainKnot.process``
           awaits ``afold(state, run_result)`` to integrate the iteration's
           outputs into the accumulated state.
        6. Plan next — ``astep(new_state)`` is awaited immediately after the fold.
           If it returns a ``(tapestry, state)`` pair, a new ``_IterationChainKnot``
           for iteration N+1 is registered into the loop's live store via
           ``Tapestry.current_store()``.  The extensible engine merges it as soon as
           iteration N's completion is processed and starts it straight away,
           with the previous iteration knot as its parent edge (encoding the
           data dependency and ordering).
        7. Terminal registration — when ``step`` returns ``None``, a
           ``_LoopTerminal`` knot is registered with the last iteration chain
           knot as its ``state`` parent.  The terminal's ID is the well-known
           sentinel ``__loop_terminal__``.
        8. Output extraction — ``_resolve_output_key`` always returns
           ``_terminal_id`` so the final state surfaced by ``_LoopTerminal``
           becomes the loop's output, regardless of how many iterations ran.
    """

    _extensible_inner_run: ClassVar[bool] = True
    _terminal_id: ClassVar[str] = "__loop_terminal__"

    #: Whether a failed iteration is survivable.
    #:
    #: ``False`` (the default) preserves the original behaviour: any failed
    #: iteration raises ``SubTapestryError`` and kills the whole loop.
    #:
    #: Set ``True`` to hand the failed ``RunResult`` to ``fold`` instead, with
    #: ``succeeded is False`` and a populated ``exceptions``.  ``fold`` then
    #: decides — return state that makes ``step`` retry, or state that makes it
    #: terminate.  This is what makes retry-until-success expressible: a flaky
    #: provider call, a timeout, a tool error or a rate limit is a *legitimate
    #: retry trigger*, and without this the loop could not see it at all.
    #:
    #: Opt-in rather than default because tolerating a failure silently is the
    #: wrong answer for a loop that has no retry logic — it would turn a real
    #: error into a quietly wrong final state.  See PIR-772.
    _tolerate_iteration_failures: ClassVar[bool] = False

    def _resolve_output_key(self, sink: Knot) -> str:
        return self._terminal_id

    def step(self, state: S) -> tuple[Tapestry, S] | None:
        """Build the next iteration's graph, or return None to terminate.

        Override this, or ``astep`` when planning must await.  May itself be
        declared ``async def``; the framework awaits the result either way.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement step() or astep()")

    def fold(self, state: S, result: RunResult) -> S:
        """Integrate an iteration's result into state.

        Override this, or ``afold`` when folding must await.  May itself be
        declared ``async def``; the framework awaits the result either way.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement fold() or afold()")

    async def astep(self, state: S) -> tuple[Tapestry, S] | None:
        """Awaitable ``step``: what the framework calls to plan the next iteration.

        The default delegates to ``step`` and awaits its result when that is
        awaitable, so a subclass overrides whichever form it needs.

        Args:
            state: The state to plan from.

        Returns:
            ``(tapestry, state)`` for the next iteration, or ``None`` to end.
        """
        outcome: Any = self.step(state)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        return outcome

    async def afold(self, state: S, result: RunResult) -> S:
        """Awaitable ``fold``: what the framework calls to integrate an iteration.

        The default delegates to ``fold`` and awaits its result when that is
        awaitable, so a subclass overrides whichever form it needs.

        Args:
            state: The state the iteration was planned from.
            result: The iteration run's result.

        Returns:
            The state the next ``astep`` receives.
        """
        folded: Any = self.fold(state, result)
        if inspect.isawaitable(folded):
            folded = await folded
        return folded

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
        # Prefer the live contextvar over the construction-time capture, for the
        # same reason `SubTapestry._run_inner` does (PIR-764): a loop built
        # inside another SubTapestry's `process()` captured the throwaway
        # `with Tapestry() as inner:` that `__call__` opens, which is discarded
        # when that outer inner-run ends — so every iteration run below it was
        # recorded into a store nobody keeps. PIR-764 fixed `_run_inner`; this
        # call site had no consumer to expose it until the PIR-713 pilot nested
        # a loop inside a pipeline.
        from pirn.tapestry import _current_history

        outer_history: Any = _current_history.get(None)
        if outer_history is None:
            outer_history = self._mutable_outer_history

        first_outcome = await self.astep(state)
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
