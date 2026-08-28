"""LoopSubTapestry — an iterative SubTapestry for agentic and feedback-loop patterns.

The pattern separates into two pure functions that the framework threads together:

    step(state: S) -> tuple[Tapestry, S] | None
        Decide what to do next.  Build the inner tapestry for this iteration
        and return it alongside the updated state that ``fold`` will receive.
        Return ``None`` to terminate — the current state becomes the final result.

    fold(state: S, result: RunResult) -> S
        Integrate the iteration's outcome into state.  The returned value is
        passed to the next ``step`` call.

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

    ``state`` is always the single declared input, and is always a plain config
    value: the second element of the tuple ``step`` returned for this iteration.
    That is what ``fold`` receives, per the contract in the module docstring.

    Sequencing is carried separately by the ``_previous_iteration`` implicit
    parent, so iteration N+1 cannot begin before iteration N completes.  These
    two concerns used to share one wiring — ``state=self`` — which meant
    ``step``'s returned state was silently discarded for every iteration after
    the first (PIR-754).
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
        from pirn.core.run_request import RunRequest
        from pirn.nodes.sub_tapestry import _apply_inherited_value_plane, _inherited_emitters
        from pirn.tapestry import (
            _current_data_store,
            _current_emitter_error_policy,
            _current_emitters,
            _current_history,
            _current_run_id,
            _current_traceback_filter,
            _current_transport,
        )

        loop: LoopSubTapestry = object.__getattribute__(self, "_mutable_loop_sub")  # type: ignore[type-arg]
        iter_tapestry: Tapestry = object.__getattribute__(self, "_mutable_iter_tapestry")
        iteration_idx: int = object.__getattribute__(self, "_mutable_iteration_idx")
        outer_history: Any = object.__getattribute__(self, "_mutable_outer_history")

        if outer_history is None:
            outer_history = _current_history.get(None)
        if outer_history is not None:
            # Always record.  This used to be skipped when the store was an
            # InMemoryHistory, on the sound reasoning that an open-ended loop
            # accumulates one child run per turn and an ephemeral store cannot
            # absorb that.  But InMemoryHistory is the *default* backend, so the
            # effect was that a conversational loop was silently unobservable
            # out of the box — and a concrete-type check here cannot recognise
            # an ephemeral backend core has never heard of.
            #
            # The growth guard now lives where it belongs: the store declares a
            # `retention` capability and keeps a bounded window. Recording is
            # bounded rather than absent. See PIR-765.
            iter_tapestry._history = outer_history

        # The value plane is inherited from the contextvars alone, with no
        # construction-time capture, for the same reason as emitters below: the
        # vars are set by the loop's own inner run, which
        # ``SubTapestry._run_inner`` already seeded from the outer run, so they
        # are correct at every nesting depth.  Without this an iteration's
        # outputs go to a fresh ``InMemoryDataStore`` that dies with the
        # iteration, while its lineage rows are recorded in the outer history
        # and keep naming hashes nobody can resolve (PIR-837).  An iteration
        # tapestry that named its own transport in ``step()`` keeps it.
        _apply_inherited_value_plane(
            iter_tapestry,
            data_store=_current_data_store.get(None),
            transport=_current_transport.get(None),
        )

        # Emitters are inherited from the contextvar alone, with no
        # construction-time capture to fall back on.  The var is set by the
        # loop's own inner run, which `SubTapestry._run_inner` already seeded
        # with the outer subscription, so it is correct at every nesting depth
        # and needs no threading through `_IterationChainKnot.__init__` the way
        # `_outer_history` does.  A dispatcher that crosses a process boundary
        # starts from an empty context and so inherits nothing — which is the
        # only honest answer for emitters, since an arbitrary emitter is not
        # transferable to another interpreter.
        #
        # Forwarding here is unconditional, so a conversational loop delivers
        # one `on_run_result` per turn.  That is the intended volume, not an
        # oversight: see the rationale on `SubTapestry._run_inner` (PIR-834).
        # The `RunRetention` guard (PIR-765) that bounds history growth has no
        # emitter analogue, because emitters are always explicitly attached and
        # their intake is proportional to work the loop actually performed.
        # Consumers that need a ceiling can filter on `RunResult.parent_run_id`.
        inherited = _inherited_emitters(iter_tapestry.emitters, _current_emitters.get(None))
        parent_run_id = _current_run_id.get(None)
        result = await iter_tapestry.run(
            RunRequest(),
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
            # Same inheritance as SubTapestry._run_inner — see PIR-725.
            traceback_filter=_current_traceback_filter.get(None),
            emitters=inherited,
            emitter_error_policy=(
                _current_emitter_error_policy.get(None) if inherited is not None else None
            ),
        )
        if not result.succeeded and not loop._tolerate_iteration_failures:
            from pirn.nodes.sub_tapestry import SubTapestryError

            raise SubTapestryError(result)

        # When the loop tolerates failures, the failed RunResult is handed to
        # `fold` unchanged — `succeeded is False` with a populated `exceptions`
        # — so the loop itself decides whether that is a retry trigger or a
        # reason to stop.  See PIR-772.
        new_state = loop.fold(state, result)

        store = get_current_store()
        if store is None:
            return new_state

        next_idx = iteration_idx + 1
        next_outcome = loop.step(new_state)
        next_knot_id = loop.step_id(new_state, next_idx)

        if next_outcome is not None:
            next_tapestry, next_state = next_outcome
            next_knot = _IterationChainKnot(
                _loop_sub=loop,
                _iter_tapestry=next_tapestry,
                _iteration_idx=next_idx,
                _outer_history=outer_history,
                # ``state`` is the state ``step`` returned, matching iteration 1
                # (see ``_first_iteration_knot``) and the documented contract:
                # "return it alongside the updated state that ``fold`` will
                # receive".  Passing ``self`` here instead silently dropped that
                # second tuple element for every iteration after the first.
                state=next_state,
                # Ordering only.  ``state`` used to double as the sequencing edge;
                # now that it carries a value, the chain needs its own explicit
                # parent so iteration N+1 still cannot start before iteration N.
                _previous_iteration=self,
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

    The base class owns the iteration loop, history injection, and run
    recording.  Subclasses never call ``_run_inner`` directly.

    Algorithm:
        1. Bootstrap — ``process()`` calls ``step(initial_state)`` to decide
           whether any iterations are needed.
        2. Zero-iteration short-circuit — if ``step`` returns ``None`` on the
           first call, a ``_LoopTerminal`` seeded with the initial state is
           registered directly in the inner tapestry and returned as the sink.
           The loop run completes in a single wave.
        3. First iteration — otherwise, an ``_IterationChainKnot`` for iteration
           index 1 is created with the iteration tapestry returned by ``step``
           and registered in the inner tapestry.  The initial state is wired in
           as a config value (not a parent edge) so no upstream dependency exists.
        4. Extensible inner run — ``SubTapestry.__call__`` starts the inner
           tapestry in extensible mode (``_extensible_inner_run = True``).  The
           engine executes iteration 1 and waits for more knots.
        5. Fold — when iteration N completes, ``_IterationChainKnot.process``
           calls ``fold(state, run_result)`` to integrate the iteration's outputs
           into the accumulated state.
        6. Plan next — ``step(new_state)`` is called immediately after ``fold``.
           If it returns a ``(tapestry, state)`` pair, a new ``_IterationChainKnot``
           for iteration N+1 is registered into the loop's live store via
           ``get_current_store()``.  The extensible engine picks it up in the
           next wave, with the previous iteration knot as its parent edge
           (encoding the data dependency and ordering).
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
            outer_history = object.__getattribute__(self, "_mutable_outer_history")

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
