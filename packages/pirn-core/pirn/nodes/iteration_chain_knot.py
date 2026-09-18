"""``IterationChainKnot`` — one link in a ``LoopSubTapestry`` chain."""

from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_context_vars import RunContextVars
from pirn.nodes.loop_iteration_plan import LoopIterationPlan
from pirn.nodes.loop_terminal import LoopTerminal
from pirn.tapestry import Tapestry

#: The loop state type, shared with the ``LoopSubTapestry`` the chain belongs to.
S = TypeVar("S")


class IterationChainKnot(Knot, Generic[S]):
    """One link in a LoopSubTapestry chain.

    Runs its pre-planned iteration tapestry, folds the result into state,
    plans the next iteration via ``step``, and self-registers the successor
    into the loop tapestry's store for the extensible engine to pick up.

    ``state`` is a plain config value: the second element of the tuple ``step``
    returned for this iteration.  That is what ``fold`` receives, per the
    contract in the module docstring.  The iteration's other declared input is
    its ``LoopIterationPlan`` — the loop, that iteration's planned tapestry, its
    index and the history to record it in — which is one opaque value rather
    than four hidden ``_mutable_`` slots.

    Sequencing is carried separately by the ``_previous_iteration`` implicit
    parent, so iteration N+1 cannot begin before iteration N completes.  These
    two concerns used to share one wiring — ``state=self`` — which meant
    ``step``'s returned state was silently discarded for every iteration after
    the first (PIR-754).

    An iteration is a container: it holds no admission slot while its
    iteration run executes, and that run inherits the loop run's execution
    plane -- the same shared gate, dispatcher, observers, replay posture and
    resolver -- through ``Tapestry.run`` (ADR agents-speaks-core, WS0b).  An
    iteration tapestry built as ``Tapestry(dispatcher=..., concurrency=...)``
    inside ``step()`` keeps what it named, exactly as it keeps a transport.
    """

    _holds_admission_slot: ClassVar[bool] = False

    async def process(self, state: Any, plan: LoopIterationPlan[S], **_: Any) -> Any:
        """Run this iteration's tapestry, fold the result into state, and register the next iteration or terminal knot.

        Args:
            state: Current loop state, either the initial value or the folded output of the previous iteration.
            plan: This iteration's non-graph context — the loop, the tapestry
                its graph was planned into, which iteration it is, and the
                history its inner run is recorded in.  A declared input rather
                than four ``_mutable_`` slots, so ``process()`` can be called
                standalone with plain values and the plan is validated and
                recorded like any other input (PIR-873).

        Returns:
            Updated state value produced by folding this iteration's RunResult.
        """
        from pirn.core.run_request import RunRequest
        from pirn.nodes.nested_run_knot import NestedRunKnot

        loop = plan.loop
        iter_tapestry = plan.tapestry
        iteration_idx = plan.index
        outer_history = plan.history

        if outer_history is None:
            outer_history = RunContextVars.history.get(None)
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
            iter_tapestry.adopt_history(outer_history)

        # The value plane is inherited from the contextvars alone, with no
        # construction-time capture, for the same reason as emitters below: the
        # vars are set by the loop's own inner run, which
        # ``SubTapestry._run_inner`` already seeded from the outer run, so they
        # are correct at every nesting depth.  Without this an iteration's
        # outputs go to a fresh ``InMemoryDataStore`` that dies with the
        # iteration, while its lineage rows are recorded in the outer history
        # and keep naming hashes nobody can resolve (PIR-837).  An iteration
        # tapestry that named its own transport in ``step()`` keeps it.
        #
        # Inheriting the outer store hands it every turn's values, which on an
        # open-ended loop never stops.  That growth is bounded the same way the
        # history growth above is: the store declares a `retention` capability
        # and evicts to stay within it, so the value plane is bounded rather
        # than either unbounded or thrown away.  See PIR-839.
        iter_tapestry.adopt_value_plane(
            data_store=RunContextVars.data_store.get(None),
            transport=RunContextVars.transport.get(None),
        )

        # Emitters are inherited from the contextvar alone, with no
        # construction-time capture to fall back on.  The var is set by the
        # loop's own inner run, which `SubTapestry._run_inner` already seeded
        # with the outer subscription, so it is correct at every nesting depth
        # and needs no threading through `IterationChainKnot.__init__` the way
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
        inherited = NestedRunKnot.inherited_emitters(
            iter_tapestry.emitters, RunContextVars.emitters.get(None)
        )
        parent_run_id = RunContextVars.run_id.get(None)
        # No ``_nesting_key``: an iteration run counts one level of nesting
        # depth but adds nothing to the guard's path -- the loop's own class is
        # already there, and a loop inside another loop's iteration is not a
        # cycle (``RunNesting``).
        result = await iter_tapestry.run(
            RunRequest(),
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
            # Same inheritance as SubTapestry._run_inner — see PIR-725.
            traceback_filter=RunContextVars.traceback_filter.get(None),
            emitters=inherited,
            emitter_error_policy=(
                RunContextVars.emitter_error_policy.get(None) if inherited is not None else None
            ),
        )
        if not result.succeeded and not loop.tolerates_iteration_failures():
            from pirn.nodes.sub_tapestry_error import SubTapestryError

            raise SubTapestryError(result)

        # When the loop tolerates failures, the failed RunResult is handed to
        # `fold` unchanged — `succeeded is False` with a populated `exceptions`
        # — so the loop itself decides whether that is a retry trigger or a
        # reason to stop.  See PIR-772.
        new_state = await loop.afold(state, result)

        store = Tapestry.current_store()
        if store is None:
            return new_state

        next_idx = iteration_idx + 1
        next_outcome = await loop.astep(new_state)
        next_knot_id = loop.step_id(new_state, next_idx)

        if next_outcome is not None:
            next_tapestry, next_state = next_outcome
            next_knot: IterationChainKnot[S] = IterationChainKnot(
                plan=plan.next_plan(tapestry=next_tapestry, history=outer_history),
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
            # ``loop.terminal_id()``, not the base class's: a subclass that
            # overrides ``_terminal_id`` has ``_resolve_output_key`` looking for
            # *its* id, so registering the terminal under the base id made the
            # loop's output lookup a KeyError (PIR-873).
            store.register(LoopTerminal(state=self, _config=KnotConfig(id=loop.terminal_id())))

        return new_state
