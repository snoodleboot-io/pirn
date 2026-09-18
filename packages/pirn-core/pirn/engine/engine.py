"""The engine — shed walker with lineage capture.

Given a list of terminal knots, a ``RunRequest``, and the run-scoped
backends (``RunHistory``, ``DataStore``), the engine:

1. Builds a ``Shed`` by walking parents from the terminals — the
   per-run cross-section of the tapestry that will execute.
2. Binds ``Parameter`` knots from the request.
3. Walks the shed in topological order, dispatching each knot when its
   parents resolve, applying each knot's ``error_policy`` and the
   ``Optional`` mixin's skip-vs-fail semantics.
4. Captures a ``KnotLineage`` record per knot per execution, with
   content-addressed input/output hashes.
5. Persists the final ``RunResult`` via ``RunHistory.record_run``.

Concurrency model: an admission queue (PIR-841).  A knot becomes ready the
moment its last parent resolves and waits in a ``ReadyQueue`` until the run's
``Admission`` admits it; only then is it decided, materialized and
dispatched as an ``asyncio`` task.  Completions are processed one at a time as
they happen, so a knot's children start as soon as *their* parents are done,
never held back by an unrelated slow knot.  The default gate admits everything.

Per-knot records (lineage, exceptions, skips, outputs) are reported in an
order derived from the graph alone -- ``DependencyTracker.sort_key`` -- so it
does not depend on completion order.  Status events are the exception: they
are the live transition stream, and arrive in the order transitions happen.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.concurrency.unused_concurrency_group_warning import UnusedConcurrencyGroupWarning
from pirn.core.content_hasher import ContentHasher
from pirn.core.err import Err
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.core.result import Result
from pirn.core.run_context import RunContext
from pirn.core.run_context_vars import RunContextVars
from pirn.core.run_nesting import RunNesting
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.core.skipped import Skipped
from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.inline_transport import InlineTransport
from pirn.core.transport.transport_handle import TransportHandle
from pirn.emitters.emitter import Emitter
from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.engine.admission.admission import Admission
from pirn.engine.admission.admission_observer import AdmissionObserver
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.admission_ticket_holder import AdmissionTicketHolder
from pirn.engine.admission.limited_admission import LimitedAdmission
from pirn.engine.admission.unbounded_admission import UnboundedAdmission
from pirn.engine.admission_feedback import AdmissionFeedback
from pirn.engine.dispatchers.dispatcher import Dispatcher
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.engine.emitter_fanout import EmitterFanout
from pirn.engine.governed_dispatch import GovernedDispatch
from pirn.engine.lineage_recorder import LineageRecorder
from pirn.engine.run_scoped_subscriber import RunScopedSubscriber
from pirn.engine.scheduling.dependency_tracker import DependencyTracker
from pirn.engine.scheduling.ready_queue import ReadyQueue
from pirn.engine.shed.shed import Shed
from pirn.exceptions.unbound_parameter_error import UnboundParameterError
from pirn.managers.knot_state import KnotState
from pirn.managers.rebindable_error import RebindableError
from pirn.recording.replay_session import ReplaySession

_log = logging.getLogger(__name__)


class Engine:
    """Async shed walker.  Owns no state across runs."""

    def __init__(self, dispatcher: Dispatcher | None = None) -> None:
        self._dispatcher = dispatcher or LocalDispatcher()
        # Every dispatch goes through the governed path, which applies the
        # knot's ``KnotConfig.timeout`` and ``KnotConfig.retry`` around the
        # dispatcher (ADR agents-speaks-core, WS0).
        self._governed = GovernedDispatch(self._dispatcher)

    async def execute(
        self,
        terminals: list[Knot],
        request: RunRequest,
        history: RunHistory,
        data_store: DataStore,
        emitters: list[Emitter] | None = None,
        extensible_store: Any = None,
        traceback_filter: Callable[[str], str] | None = None,
        emitter_error_policy: EmitterErrorPolicy = EmitterErrorPolicy.WARN,
        parent_run_id: str | None = None,
        parent_knot_id: str | None = None,
        transport: DataTransport | None = None,
        actor: str | None = None,
        replay: ReplaySession | None = None,
        concurrency: ConcurrencyLimits | None = None,
        nesting: RunNesting | None = None,
        admission_observers: list[AdmissionObserver] | None = None,
        gate: Admission | None = None,
        limits_inherited: bool = False,
    ) -> RunResult:
        """Run the shed rooted at *terminals* and return its ``RunResult``.

        ``gate`` is the admission gate this run is metered by.  ``Tapestry.run``
        passes the one it resolved -- built from *concurrency* for a run with
        limits of its own, or the enclosing run's very instance for an inner
        run that declared none (ADR agents-speaks-core, WS0b) -- and sets
        ``limits_inherited`` in the second case so the group check below can
        tell an inherited group nobody here uses from a misnamed one.  When
        ``gate`` is ``None`` the engine builds one from *concurrency*.
        """
        shed = Shed.from_terminals(terminals)
        active_gate = gate if gate is not None else self.gate_for(concurrency)
        self._check_groups(
            shed,
            concurrency,
            active_gate,
            extensible=extensible_store is not None,
            inherited=limits_inherited,
        )

        ctx = RunContext(
            run_id=request.run_id,
            terminals_requested=[t.knot_id for t in terminals],
            dispatcher_name=self._dispatcher.name,
            parameters=dict(request.parameters),
            traceback_filter=traceback_filter,
            parent_run_id=parent_run_id,
            parent_knot_id=parent_knot_id,
            actor=actor,
            trigger=request.trigger,
            nesting=nesting,
        )

        # Wire emitters' on_status to the StatusManager.  Async emitters
        # need to be invoked from a sync subscriber (StatusManager calls
        # subscribers synchronously); we schedule a task per event.
        emitters = emitters or []
        if emitters:
            EmitterFanout.subscribe_emitters_to_status(ctx, emitters, emitter_error_policy)

        # Mid-run extension: subscribe to the store if one was provided.
        # New knots arriving during the run go into ``pending_new`` and
        # are merged into the shed as knots complete.  The store is
        # tapestry-scoped and fans every registration to every
        # subscriber, so the callback filters to this run's own
        # registrations -- otherwise concurrent extensible runs execute
        # each other's knots (PIR-808).
        pending_new: list[Knot] = []
        registrars: dict[str, str] = {}
        subscribe_token = None
        if extensible_store is not None:
            from pirn.backends.base.subscribable_store import SubscribableStore

            if not isinstance(extensible_store, SubscribableStore):
                raise TypeError(
                    "extensible_store must implement subscribe / unsubscribe; "
                    "the InMemoryStore is the reference implementation"
                )

            subscribe_token = extensible_store.subscribe(
                RunScopedSubscriber(ctx.run_id, pending_new, registrars)
            )

        active_transport: DataTransport = transport or InlineTransport()
        try:
            return await self._execute_loop(
                shed=shed,
                ctx=ctx,
                history=history,
                data_store=data_store,
                emitters=emitters,
                pending_new=pending_new,
                request=request,
                emitter_error_policy=emitter_error_policy,
                transport=active_transport,
                replay=replay,
                registrars=registrars,
                gate=active_gate,
                admission_observers=admission_observers,
            )
        finally:
            if extensible_store is not None and subscribe_token is not None:
                extensible_store.unsubscribe(subscribe_token)

    async def _execute_loop(
        self,
        shed: Shed,
        ctx: RunContext,
        history: RunHistory,
        data_store: DataStore,
        emitters: list[Emitter],
        pending_new: list[Knot],
        request: RunRequest,
        emitter_error_policy: EmitterErrorPolicy = EmitterErrorPolicy.WARN,
        transport: DataTransport | None = None,
        replay: ReplaySession | None = None,
        registrars: dict[str, str] | None = None,
        gate: Admission | None = None,
        admission_observers: list[AdmissionObserver] | None = None,
    ) -> RunResult:
        active_transport: DataTransport = transport or InlineTransport()
        await active_transport.begin_run(ctx.run_id)

        # Bind parameters.  Setup-time errors propagate; recovery is the
        # caller's job (correct an unbound parameter and try again).
        self._bind_parameters(shed, ctx)

        # results[knot_id] holds Ok | Err | Skipped, or absent if not yet
        # considered.  We use the same dict for lineage I/O hash lookups.
        results: dict[str, Result[Any]] = {}

        # handles[knot_id] holds the TransportHandle for that knot's output,
        # written after each successful knot execution.
        handles: dict[str, TransportHandle] = {}

        # handle_transports[knot_id] records which transport wrote that knot's
        # output so _materialize can read from the correct backend.  Defaults
        # to active_transport; overridden per-knot via KnotConfig.transport.
        handle_transports: dict[str, DataTransport] = {}

        # started_transports tracks per-knot transports that have had
        # begin_run called so we can call end_run on them at cleanup.
        started_transports: dict[int, DataTransport] = {id(active_transport): active_transport}

        # The admission loop (PIR-841).  A knot enters the ready queue the
        # moment its last parent resolves, and is decided, materialized and
        # dispatched only once the gate admits it.  Each completion is
        # processed as soon as it happens: its value is stored, its lineage
        # recorded, and its children released.  So a child never waits for an
        # unrelated slow sibling of its parent, which the wave loop this
        # replaced made it do.
        tracker = DependencyTracker(shed)
        ready = ReadyQueue()
        if gate is None:
            gate = UnboundedAdmission()
        # Admission feedback (WS0): every admission and release is reported to
        # the run's observers with queue depth, wait, hold time and outcome,
        # so an adaptive controller can steer ``gate.set_limit``.  Silent and
        # free when nobody is listening.
        feedback = AdmissionFeedback(ctx.run_id, gate, admission_observers or ())
        self._enqueue(ready, tracker, shed, tracker.initially_ready(), feedback)

        # In-flight tasks, each with the knot instance this run actually
        # dispatched -- kept so lineage is read back off the copy that executed
        # rather than off the shared graph knot (``Knot.run_scoped_copy``,
        # PIR-809) -- and a holder for the ticket its admission issued.  A
        # holder, not the ticket itself, because a retrying knot's ticket may
        # be swapped mid-flight: released for the backoff sleep and replaced
        # by a freshly re-admitted one before the next attempt (PIR-870), so
        # whatever is current when the task completes is what gets released.
        running: dict[
            asyncio.Task[tuple[Result[Any], dict[str, str], datetime, bool, datetime]],
            tuple[Knot, AdmissionTicketHolder],
        ] = {}
        completions: asyncio.Queue[
            asyncio.Task[tuple[Result[Any], dict[str, str], datetime, bool, datetime]]
        ] = asyncio.Queue()
        # Ids of knots that were dispatched rather than resolved by the engine
        # without running; part of the reporting order (see ``sort_key``).
        dispatched: set[str] = set()
        # Mid-run registrations made from inside a dispatched knot, keyed
        # newcomer id -> registering knot id.  Filled by the store subscriber.
        known_registrars: dict[str, str] = registrars if registrars is not None else {}
        # A ticket admitted but not yet handed to an in-flight task or back to
        # the gate.  Admission awaits (materialization) before the task exists,
        # so an abort in that window must still give the slot back.
        unplaced: AdmissionTicket | None = None

        try:
            while True:
                # Mid-run extension.  A new knot whose parent already completed
                # is served from that result; a parent that is neither resolved
                # nor in the shed is a hard error raised by ``_merge_new_knots``.
                if pending_new:
                    newcomers = self._absorb_pending(
                        shed,
                        pending_new,
                        known_registrars,
                        results,
                        ctx,
                        tracker,
                    )
                    self._enqueue(ready, tracker, shed, newcomers, feedback)

                # Admit everything the gate allows.  A knot the engine resolves
                # without dispatching (skipped, or failed for a missing parent)
                # gives its ticket straight back and may release children into
                # this same pass.
                #
                # Container knots (SubTapestry, LoopSubTapestry, a loop
                # iteration) are slot-free: the queue admits them without the
                # gate and their ticket is never released to it.  Their inner
                # runs share this very gate (ADR agents-speaks-core, WS0b), so
                # every slot holder is a leaf that is actually running and an
                # open-ended loop under a small cap cannot starve its siblings
                # by sitting on a slot while it waits for its own leaves.
                while (admitted := ready.pop_admissible(gate, shed)) is not None:
                    kid, unplaced = admitted
                    knot = shed.knot(kid)
                    ctx.status.transition(kid, KnotState.RUNNING)
                    feedback.admitted(kid, unplaced, ready.waiting_in(unplaced.group))

                    decision = self._decide(shed, knot, results, ctx)

                    if isinstance(decision, (Skipped, Err)):
                        self._release(gate, ready, unplaced)
                        results[kid] = decision
                        if isinstance(decision, Skipped):
                            ctx.skipped.append(kid)
                            ctx.status.transition(kid, KnotState.SKIPPED, decision.reason)
                            feedback.released(unplaced, "skipped", ready.waiting_in(unplaced.group))
                        else:
                            # REQUIRE_ALL_PARENTS: synthetic Err.
                            ctx.status.transition(kid, KnotState.FAILED, "missing parent")
                            feedback.released(unplaced, "err", ready.waiting_in(unplaced.group))
                        unplaced = None
                        row = LineageRecorder.record_lineage(
                            ctx, knot, results, decision, started=ctx.started_at
                        )
                        # The knot settled without running; stream its outcome
                        # now, like any other (WS0b).
                        await EmitterFanout.emit_knot_result(
                            emitters, emitter_error_policy, kid, decision, row
                        )
                        self._enqueue(ready, tracker, shed, tracker.resolve(kid), feedback)
                        continue

                    # decision is the resolved input dict.
                    # Materialize each parent value through the transport before
                    # dispatching so non-inline transports read from their store.
                    materialized = await self._materialize(
                        knot, decision, shed, handles, handle_transports, active_transport
                    )
                    # Dispatch a copy so run-derived state the knot stashes for
                    # ``lineage_extra`` lands on something this run owns.  Several
                    # knots write that state onto ``self``, and it is read back
                    # only after the task completes -- long enough for a concurrent
                    # run to overwrite it on the shared graph knot (PIR-809).
                    run_knot = knot.run_scoped_copy()
                    dispatched.add(kid)
                    holder = AdmissionTicketHolder(unplaced)
                    task = asyncio.create_task(
                        self._invoke_admitted(
                            run_knot, materialized, replay, data_store, gate, holder
                        )
                    )
                    running[task] = (run_knot, holder)
                    unplaced = None
                    task.add_done_callback(completions.put_nowait)

                if not running:
                    if pending_new:
                        continue
                    if ready:
                        # Refused with nothing in flight to free capacity.
                        # Nothing in flight means nothing will unpark a group
                        # either, so re-offer them all.
                        ready.unpark_all()
                        await gate.wait_for_release()
                        continue
                    break

                # Each task reports itself on ``completions`` when it finishes,
                # so waking costs O(1) per completion.  ``asyncio.wait`` would
                # re-attach a callback to every in-flight task on each wake.
                # While ready knots sit refused behind a full gate, also wake
                # on a release: the gate is shared with the enclosing and
                # sibling runs (WS0b), so the slot they need may be freed by
                # a completion this run never sees.
                done = await self._next_completions(completions, gate, waiting=bool(ready))
                if not done:
                    # Woken by a release, possibly of another run's group
                    # slot: nothing here knows which, so re-offer them all.
                    ready.unpark_all()
                    continue
                # Several tasks can finish in one tick; process them in
                # topological order so the run's side effects are reproducible.
                for task in sorted(done, key=lambda t: tracker.topo_index(running[t][0].knot_id)):
                    knot, holder = running.pop(task)
                    kid = knot.knot_id
                    # Release before reading the outcome, so the slot comes back
                    # however the task ended -- a result, an Err, or an exception
                    # or cancellation that ``task.result()`` re-raises below.  It
                    # does not rely on ``Knot.__call__`` catching anything.  Read
                    # off the holder, not a ticket captured at admission time: a
                    # retry may have swapped it for a freshly re-admitted one
                    # (PIR-870).
                    ticket = holder.ticket
                    self._release(gate, ready, ticket)
                    result, parent_hashes, started_at, replayed, finished_at = task.result()
                    # Re-register placeholder records with the live manager.
                    result = self._rebind_err(result, kid, ctx)
                    results[kid] = result
                    feedback.released(
                        ticket, self._outcome_name(result), ready.waiting_in(ticket.group)
                    )

                    if isinstance(result, Ok):
                        ctx.status.transition(kid, KnotState.SUCCEEDED)
                        # Persist value to data store keyed by hash.
                        out_hash = ContentHasher.hash(result.value)
                        await data_store.put(out_hash, result.value)
                        # Write through transport.  Per-knot override takes
                        # priority; lazy begin_run for newly-seen transports.
                        knot_transport: DataTransport = knot.config.transport or active_transport
                        if id(knot_transport) not in started_transports:
                            await knot_transport.begin_run(ctx.run_id)
                            started_transports[id(knot_transport)] = knot_transport
                        handles[kid] = await knot_transport.write(ctx.run_id, kid, result.value)
                        handle_transports[kid] = knot_transport
                    elif isinstance(result, Skipped):
                        # A knot that runs but produces Skipped (e.g. a
                        # BranchOutput whose branch wasn't selected, a Gate
                        # that closed).  Recorded as skipped, not failed.
                        ctx.skipped.append(kid)
                        ctx.status.transition(kid, KnotState.SKIPPED, result.reason)
                    else:
                        ctx.status.transition(kid, KnotState.FAILED)

                    row = LineageRecorder.record_lineage(
                        ctx,
                        knot,
                        results,
                        result,
                        parent_hashes=parent_hashes,
                        started=started_at,
                        finished=finished_at,
                        replayed_from=replay.source_run_id if replayed and replay else None,
                    )
                    # Stream the settled outcome to the emitters now, before
                    # any child is released: a consumer of a fan-out sees each
                    # item as it finishes rather than after the join (WS0b).
                    await EmitterFanout.emit_knot_result(
                        emitters, emitter_error_policy, kid, result, row
                    )
                    self._enqueue(ready, tracker, shed, tracker.resolve(kid), feedback)
                    if pending_new:
                        newcomers = self._absorb_pending(
                            shed,
                            pending_new,
                            known_registrars,
                            results,
                            ctx,
                            tracker,
                        )
                        self._enqueue(ready, tracker, shed, newcomers, feedback)
        except BaseException:
            # The run is aborting: a replay that cannot be served, a setup
            # error in a mid-run merge, or the run itself being cancelled.
            # Cancel the knots still in flight and wait for them to wind down,
            # so their cleanup has finished before the caller sees the error.
            #
            # Only the asyncio side can be interrupted.  A knot running on a
            # worker thread (``ThreadDispatcher``, a sync ``@KnotFactory.knot`` via
            # ``asyncio.to_thread``) or on a remote worker keeps running until
            # it returns; its task completes as cancelled at once, so this wait
            # never blocks on it, but the thread itself is not stopped.
            #
            # Every slot still held comes back to the gate, so nothing waiting
            # on it -- a nested run sharing the budget (ADR agents-speaks-core,
            # WS0b) -- is left parked behind an aborted run.
            try:
                for task in running:
                    task.cancel()
                await asyncio.gather(*running, return_exceptions=True)
            finally:
                # Known limitation: a knot on a worker thread (ThreadDispatcher,
                # sync @KnotFactory.knot) is still running when its cancelled task
                # completes, yet its slot is released here.  Harmless for a
                # root run, since the run is over; a gate shared with an
                # enclosing run that carries on may briefly admit one knot
                # beside that still-running thread.
                for _, holder in running.values():
                    held = holder.ticket
                    if held.held:
                        gate.release(held)
                    feedback.released(held, "aborted", 0)
                running.clear()
                if unplaced is not None:
                    if unplaced.held:
                        gate.release(unplaced)
                    feedback.released(unplaced, "aborted", 0)
                # The status deliveries already scheduled still finish, so none
                # is left pending on the loop; the abort's error is the one
                # that propagates.
                await EmitterFanout.drain_status_deliveries(ctx, raise_failures=False)
            raise

        # Every knot has settled, so every ``on_status`` delivery of this run
        # has been scheduled.  Await them all: under ``EmitterErrorPolicy.RAISE``
        # a hook that raised fails the run here, before it is persisted, as a
        # raising ``on_knot_result`` does.
        await EmitterFanout.drain_status_deliveries(ctx)

        # Report per-knot records in an order that depends on the graph alone,
        # never on which knot finished first (PIR-841).  For a graph without
        # mid-run registrations this is exactly the order the wave loop gave;
        # registrar-less newcomers sort last (see ``_absorb_pending``).
        # Every record belongs to a knot with a result, so one key per result
        # covers them all; computed once rather than per comparison site.
        report_key = {kid: tracker.sort_key(kid, kid in dispatched) for kid in results}
        ordered_ids = sorted(results, key=report_key.__getitem__)
        ctx.lineage.sort(key=lambda rec: report_key[rec.knot_id])
        ctx.skipped.sort(key=report_key.__getitem__)
        ctx.exceptions.sort_by_knot(lambda kid: tracker.sort_key(kid, kid in dispatched))
        outputs = {
            kid: result.value for kid in ordered_ids if isinstance(result := results[kid], Ok)
        }

        run_result = ctx.finalize(outputs)
        for source_rec in ctx.knot_sources.values():
            await history.record_knot_source(source_rec)
        await history.record_run(run_result)

        succeeded = all(isinstance(r, (Ok, Skipped)) for r in results.values())
        for t in started_transports.values():
            await t.end_run(ctx.run_id, success=succeeded)

        # Fire emitter hooks for lineage and run result.  We do these
        # after history.record_run so emitters see the persisted state.
        # on_status was wired earlier as a subscriber to StatusManager.
        for emitter in emitters:
            for record in run_result.lineage:
                try:
                    await emitter.on_lineage(record)
                except Exception as exc:
                    EmitterFanout.handle_emitter_error(
                        emitter, "on_lineage", exc, emitter_error_policy
                    )
            try:
                await emitter.on_run_result(run_result)
            except Exception as exc:
                EmitterFanout.handle_emitter_error(
                    emitter, "on_run_result", exc, emitter_error_policy
                )

        return run_result

    # ------------------------------------------------------------- helpers

    @staticmethod
    async def _next_completions(
        completions: asyncio.Queue[asyncio.Task[Any]],
        gate: Admission,
        *,
        waiting: bool,
    ) -> list[asyncio.Task[Any]]:
        """Wait for the next completed task(s), or for a gate release.

        With nothing refused (``waiting`` is ``False``) this is exactly the
        original wait on the completion queue.  With ready knots refused
        behind the gate it also returns -- empty -- when the gate reports a
        release, so a run sharing its gate with an enclosing or sibling run
        (WS0b) re-offers its queue when *their* completion frees the slot.
        Without this an inner run with one leaf in flight and one refused
        waited on its own completion alone, while the sibling that could
        have freed the slot waited on it in turn.

        Args:
            completions: The run's completion queue.
            gate: The run's (possibly shared) admission gate.
            waiting: Whether ready knots are queued refused.

        Returns:
            Every task that has completed by the time one does, or ``[]``
            when woken by a release instead.
        """
        if not waiting:
            first = await completions.get()
        else:
            getter = asyncio.ensure_future(completions.get())
            release = asyncio.ensure_future(gate.wait_for_release())
            try:
                await asyncio.wait({getter, release}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                # A cancelled ``Queue.get`` leaves the queue untouched and
                # re-notifies other getters; a cancelled waiter is skipped by
                # the gate's ``_resolve_waiter``.
                for pending in (getter, release):
                    if not pending.done():
                        pending.cancel()
            if not getter.done() or getter.cancelled():
                await asyncio.gather(getter, return_exceptions=True)
                return []
            first = getter.result()
        done = [first]
        while not completions.empty():
            done.append(completions.get_nowait())
        return done

    @staticmethod
    def gate_for(limits: ConcurrencyLimits | None) -> Admission:
        """Return the admission gate that enforces *limits* for one run.

        No limits, or limits that constrain nothing, get the lock-free
        ``UnboundedAdmission``, so an unlimited run pays nothing for the
        feature.  ``Tapestry.run`` builds a run's gate here before publishing
        it on the run's ``ExecutionPlane`` for inner runs to share.
        """
        if limits is None or limits.is_unbounded:
            return UnboundedAdmission()
        return LimitedAdmission(limits)

    @staticmethod
    def _outcome_name(result: Result[Any]) -> str:
        """The outcome vocabulary lineage uses, for admission feedback."""
        if isinstance(result, Ok):
            return "ok"
        if isinstance(result, Skipped):
            return "skipped"
        return "err"

    @staticmethod
    def _release(gate: Admission, ready: ReadyQueue, ticket: AdmissionTicket) -> None:
        """Return *ticket*'s slots and re-offer whatever they could now admit.

        A freed slot can admit a knot of the ticket's own group, which the
        queue parked when it was full, and any ungrouped knot.  A slot-free
        ticket (a container knot's) holds nothing the gate could take back,
        but its completion may still have released children, so the queue is
        re-offered either way.
        """
        if ticket.held:
            gate.release(ticket)
        ready.unpark(None)
        if ticket.group is not None:
            ready.unpark(ticket.group)

    @staticmethod
    def _check_groups(
        shed: Shed,
        limits: ConcurrencyLimits | None,
        gate: Admission,
        extensible: bool,
        inherited: bool = False,
    ) -> None:
        """Fail fast on a knot in an undefined group; warn on an unused group.

        Every knot of the static graph is offered to ``gate.check_group``
        before anything runs, so a group the run's gate cannot admit -- at any
        level of a ``ChainedAdmission`` tree, not only this run's own limits --
        fails the run before a slot is taken.  A gate whose limits define no
        groups ignores tags, so the same tapestry still runs unbounded or under
        ``max_in_flight`` alone.  A knot registered mid-run is checked by the
        gate when it is admitted.

        A defined group no static knot is in warns only when the run cannot
        receive knots it has not seen: an extensible run's newcomers, or the
        inner leaves of a container knot (``SubTapestry``, ``LoopSubTapestry``)
        in the graph, may be exactly the knots that group is for -- inner runs
        share this run's gate (WS0b) -- so there it is only debug-logged.
        Limits an inner run *inherited* from the enclosing run are never
        warned about either: they were declared for the whole run tree, and
        the knots of a group may well all live in a sibling run.

        Raises:
            UndefinedConcurrencyGroupError: For the first knot, in id order,
                whose group the gate cannot admit.
        """
        ordered = [shed.knots[knot_id] for knot_id in sorted(shed.knots)]
        for knot in ordered:
            gate.check_group(knot)
        if limits is None or not limits.groups:
            return
        used: set[str] = set()
        has_container = False
        for knot in ordered:
            if not knot.holds_admission_slot():
                has_container = True
            group = knot.config.concurrency_group
            if group is not None:
                used.add(group)
        unused = sorted(set(limits.groups) - used)
        if not unused or inherited:
            return
        if extensible or has_container:
            _log.debug(
                "ConcurrencyLimits groups %s match no knot of the static graph; "
                "mid-run knots or the inner runs of a container may still join them",
                unused,
            )
            return
        Engine._warn_outside_pirn(
            f"ConcurrencyLimits define groups {unused} that no knot of this run is in, "
            "so those caps apply to nothing; check the group names",
            UnusedConcurrencyGroupWarning,
        )

    @staticmethod
    def _warn_outside_pirn(message: str, category: type[Warning]) -> None:
        """Warn, attributed to the first frame outside the pirn package.

        A fixed ``stacklevel`` would point into ``tapestry.py`` or the engine,
        which says nothing about which call chose the limits; the useful
        location is the user's call to ``Tapestry.run``.  Python 3.12+ skips
        the package's frames natively; 3.11 counts them by walking the stack.
        """
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
        if sys.version_info >= (3, 12):
            warnings.warn(message, category, skip_file_prefixes=(package_dir,))
            return
        # stacklevel=1 is this function; level 2 is sys._getframe(1).
        level = 2
        frame = sys._getframe(1)
        while frame is not None and os.path.abspath(frame.f_code.co_filename).startswith(
            package_dir
        ):
            level += 1
            frame = frame.f_back
        warnings.warn(message, category, stacklevel=level)

    @staticmethod
    def _enqueue(
        ready: ReadyQueue,
        tracker: DependencyTracker,
        shed: Shed,
        knot_ids: list[str],
        feedback: AdmissionFeedback,
    ) -> None:
        """Push knots that just became ready onto *ready* as one batch."""
        if knot_ids:
            ready.push_batch(
                (tracker.topo_index(kid), kid, shed.knots[kid].config.concurrency_group)
                for kid in knot_ids
            )
            feedback.enqueued(knot_ids)

    def _absorb_pending(
        self,
        shed: Shed,
        pending_new: list[Knot],
        registrars: dict[str, str],
        results: dict[str, Result[Any]],
        ctx: RunContext,
        tracker: DependencyTracker,
    ) -> list[str]:
        """Merge queued mid-run registrations and return those ready at once.

        A newcomer registered from inside a dispatched knot is placed one level
        past that knot, which is exactly the wave the old loop would have run
        it in and is known regardless of which knot finished first.

        A newcomer with no known registrar -- registered from a plain thread
        or an external orchestrator, or delivered by a durable store
        (Postgres, ValKey) whose notices do not say which knot registered --
        has no position in the graph that timing does not decide.  It is
        reported in a final bucket after every knot with a known level,
        ordered by registration sequence and then knot id, so its place in the
        record order never depends on how far unrelated work has got.  This
        deliberately differs from the wave loop, whose placement was just as
        timing-dependent but hidden by coarse waves.  Scheduling is unchanged:
        the newcomer still starts as soon as its parents have resolved.
        """
        # Take exactly the registrations present now.  A worker thread may
        # append while this runs; appends only ever extend the tail, so
        # deleting the counted prefix keeps them for the next drain.  Copying
        # and then clearing would drop them.
        count = len(pending_new)
        batch = pending_new[:count]
        del pending_new[:count]
        added = self._merge_new_knots(shed, batch, results, ctx)
        if not added:
            return []
        self._bind_parameters(shed, ctx)
        # Registration order is the batch order: the subscriber appends as
        # registrations arrive.
        in_registration_order = [k.knot_id for k in batch if k.knot_id in added]
        attributed = {
            kid: registrars.pop(kid) for kid in in_registration_order if kid in registrars
        }
        return tracker.merge(in_registration_order, attributed)

    async def _invoke_admitted(
        self,
        knot: Knot,
        inputs: dict[str, Any],
        replay: ReplaySession | None,
        data_store: DataStore,
        gate: Admission,
        ticket_holder: AdmissionTicketHolder,
    ) -> tuple[Result[Any], dict[str, str], datetime, bool, datetime]:
        """Run ``_invoke`` as an admitted knot's task and stamp its finish time.

        ``finished_at`` is taken here, the instant the knot's outcome exists,
        rather than when the engine gets round to processing the completion.
        The wave loop stamped it on processing, so a fast knot listed after a
        slow sibling reported the sibling's duration as its own (PIR-841).

        The knot's id is published on ``RunContextVars.dispatching_knot_id`` for the
        life of this task, so a knot this one registers mid-run is attributed
        to it.  The task runs in its own copy of the context, so the value is
        never visible to the engine loop or to sibling knots.

        *gate* and *ticket_holder* let a retry release its admission slot
        during backoff and re-admit before the next attempt (PIR-870); see
        ``GovernedDispatch``.
        """
        RunContextVars.dispatching_knot_id.set(knot.knot_id)
        result, parent_hashes, started_at, replayed = await self._invoke(
            knot, inputs, replay, data_store, gate, ticket_holder
        )
        return result, parent_hashes, started_at, replayed, datetime.now(UTC)

    async def _materialize(
        self,
        knot: Knot,
        decision: dict[str, Any],
        shed: Shed,
        handles: dict[str, TransportHandle],
        handle_transports: dict[str, DataTransport],
        default_transport: DataTransport,
    ) -> dict[str, Any]:
        """Read each parent value through the transport before dispatch.

        For ``InlineTransport`` this is a trivial pass-through (the handle
        carries the value in-memory).  For other transports the value is
        fetched from the backing store (disk, Valkey, etc.).

        Each parent is read from whichever transport wrote it (recorded in
        ``handle_transports``); this supports mixed-transport pipelines where
        different knots write to different backends.

        ``Result`` objects (produced under ``RECEIVE_ERRORS`` policy) are
        passed through unchanged — they are small Python objects and are
        never written to the transport.
        """
        name_to_parent = {e.name: e.parent_id for e in shed.parents_of(knot.knot_id)}
        out: dict[str, Any] = {}
        for name, value in decision.items():
            if isinstance(value, (Ok, Err, Skipped)):
                out[name] = value
                continue
            parent_id = name_to_parent.get(name)
            if parent_id is not None and parent_id in handles:
                transport_for_parent = handle_transports.get(parent_id, default_transport)
                out[name] = await transport_for_parent.read(handles[parent_id])
            else:
                out[name] = value
        return out

    def _bind_parameters(self, shed: Shed, ctx: RunContext) -> None:
        """Bind every parameter's value for *this* run.

        The value goes onto a run-scoped copy that replaces the parameter in
        this run's shed -- never onto the shared graph knot.  One ``Tapestry``
        is commonly built at startup and then serves many concurrent runs;
        binding on the shared instance let those runs overwrite each other's
        inputs while each still reported its own run id, producing wrong
        answers with no error raised (PIR-802).

        The shed is per-run and keyed by ``knot_id``, which the copy
        preserves, so edges, results and lineage are unaffected.  Called again
        after each mid-run merge; re-binding an already-bound copy is
        idempotent because the value is re-read from ``ctx.parameters``.
        """
        for knot_id, knot in list(shed.knots.items()):
            if isinstance(knot, Parameter):
                if knot.name in ctx.parameters:
                    bound = knot.bind(ctx.parameters[knot.name])
                elif knot.has_default:
                    bound = knot.default
                else:
                    raise UnboundParameterError(
                        f"parameter {knot.name!r} has no value supplied and no default"
                    )
                shed.knots[knot_id] = knot.bound_copy(bound)

    def _merge_new_knots(
        self,
        shed: Shed,
        new_knots: list[Knot],
        results: dict[str, Result[Any]],
        ctx: RunContext,
    ) -> set[str]:
        """Merge mid-run-registered knots into the shed.

        Returns the set of knot ids actually added.  Knots already in
        the shed are skipped.  A new knot whose parent already has a
        result is a setup error: silently re-running the parent would
        invalidate every consumer's input hash and confuse lineage
        across runs.  Raise ``ShedError`` clearly so the user can
        correct the registration order.
        """
        from pirn.engine.shed.edge import Edge
        from pirn.engine.shed.shed_error import ShedError

        added: set[str] = set()
        # First pass: filter to genuinely new knots.
        truly_new = [k for k in new_knots if k.knot_id not in shed.knots]
        if not truly_new:
            return added

        # Second pass: validate that every parent is resolvable — either it
        # already has a result (sequential chain pattern, e.g. LoopSubTapestry)
        # or it is in the shed / also newly arrived.
        new_ids = {k.knot_id for k in truly_new}
        for k in truly_new:
            for parent in k.parents.values():
                if parent.knot_id in results:
                    continue  # parent completed; result is available — valid
                if parent.knot_id not in shed.knots and parent.knot_id not in new_ids:
                    raise ShedError(
                        f"knot {k.knot_id!r} arrived mid-run but its parent "
                        f"{parent.knot_id!r} is not in the shed and not "
                        f"newly registered; cannot resolve"
                    )

        # Third pass: insert each new knot, building edges and updating
        # children_by_parent.  We add via direct dict mutation since
        # Shed is plain Python and we control the invariants.
        for k in truly_new:
            shed.knots[k.knot_id] = k
            shed.children_by_parent.setdefault(k.knot_id, [])
            edges: list[Edge] = []
            for input_name, parent in k.parents.items():
                edges.append(
                    Edge(
                        child_id=k.knot_id,
                        parent_id=parent.knot_id,
                        name=input_name,
                    )
                )
                shed.children_by_parent.setdefault(parent.knot_id, []).append(k.knot_id)
            shed.edges_by_child[k.knot_id] = edges
            added.add(k.knot_id)

        # Cycle re-check — same algorithm Shed uses internally.
        from pirn.engine.shed.cycle_detector import CycleDetector

        if CycleDetector.detect(list(shed.knots.keys()), shed.children_by_parent):
            raise ShedError("cycle detected after mid-run merge")

        return added

    def _decide(
        self,
        shed: Shed,
        knot: Knot,
        results: dict[str, Result[Any]],
        ctx: RunContext,
    ) -> dict[str, Any] | Skipped | Err:
        """Apply error_policy and assemble the input dict.

        Returns either:
        * a dict of resolved inputs ready for dispatch, or
        * a Skipped (knot will be skipped), or
        * an Err (synthetic failure for REQUIRE_ALL_PARENTS).
        """
        edges = shed.parents_of(knot.knot_id)
        policy = knot.config.error_policy

        parent_results: dict[str, Result[Any]] = {}
        any_skipped = False
        any_err = False
        for edge in edges:
            parent_result = results[edge.parent_id]
            parent_results[edge.name] = parent_result
            if isinstance(parent_result, Skipped):
                any_skipped = True
            elif isinstance(parent_result, Err):
                any_err = True

        if policy is ErrorPolicy.REQUIRE_ALL_PARENTS:
            if any_skipped or any_err:
                err = RuntimeError(f"knot {knot.knot_id!r}: REQUIRE_ALL_PARENTS not satisfied")
                rec = ctx.exceptions.record(knot.knot_id, err)
                return Err(record=rec)
            # All parents are Ok at this point (we returned otherwise above).
            return {name: r.value for name, r in parent_results.items() if isinstance(r, Ok)}

        if policy is ErrorPolicy.SKIP_IF_PARENT_FAILED:
            if any_skipped or any_err:
                detail = {"any_err": any_err, "any_skipped": any_skipped}
                inherited = None if any_err else self._propagated_skip_reason(parent_results)
                if inherited is not None:
                    return Skipped(reason=inherited, detail=detail, propagates=True)
                return Skipped(reason="parent_failed_or_skipped", detail=detail)
            # All parents are Ok at this point (we returned otherwise above).
            return {name: r.value for name, r in parent_results.items() if isinstance(r, Ok)}

        # RECEIVE_ERRORS: pass Result objects through unchanged.
        return dict(parent_results)

    @staticmethod
    def _propagated_skip_reason(parent_results: dict[str, Result[Any]]) -> str | None:
        """The reason a knot skipped by *parent_results* inherits, if any.

        A skip inherits its parents' reason only when every skipped parent
        marked its skip ``propagates`` and they all name the same reason — a
        ``Gate`` closed by a ``Check`` with its own ``skip_reason``, or a knot
        already skipped by one.  Mixed or unpropagated reasons fall back to
        the generic ``"parent_failed_or_skipped"``.

        Args:
            parent_results: The knot's parents' outcomes; the caller has
                already established that none is an ``Err``.

        Returns:
            The shared reason, or ``None`` when there is none to inherit.
        """
        reasons: set[str] = set()
        for parent_result in parent_results.values():
            if not isinstance(parent_result, Skipped):
                continue
            if not parent_result.propagates:
                return None
            reasons.add(parent_result.reason)
        return reasons.pop() if len(reasons) == 1 else None

    async def _invoke(
        self,
        knot: Knot,
        inputs: dict[str, Any],
        replay: ReplaySession | None,
        data_store: DataStore,
        gate: Admission,
        ticket_holder: AdmissionTicketHolder,
    ) -> tuple[Result[Any], dict[str, str], datetime, bool]:
        """Produce a knot's outcome — by executing it, or from a recording.

        Returns ``(result, parent_input_hashes, started_at, replayed)``.  When
        *replay* is ``None`` this is exactly the pre-existing dispatch path and
        ``replayed`` is always ``False``; passing a session is the only way to
        reach the substituting branch, so record/replay is additive and
        default-off.

        ``Parameter`` knots execute even under replay.  Their value comes from
        the ``RunRequest`` rather than from a parent, and no hash in the
        lineage row covers it, so substituting the recorded output would
        silently discard the parameters the caller just supplied.  They are
        bound, run, and then *checked* against the recording instead — which
        is also what makes a changed parameter fail at the parameter rather
        than somewhere downstream.

        Every other knot is served from the session and never dispatched, so
        its side effects — a network call, a counter, a write — do not happen.
        Failures to serve raise out of this coroutine and abort the run;
        replay never falls back to live execution.
        """
        if replay is None:
            result, parent_hashes, started_at = await self._dispatch_with_timing(
                knot, inputs, gate, ticket_holder
            )
            return result, parent_hashes, started_at, False

        if replay.allow_new_knots and replay.row_for(knot.knot_id) is None:
            # This knot is genuinely new to the recording — e.g. it sits
            # downstream of a HITL gate the source run suspended at, so the
            # source run never reached it.  ``allow_new_knots`` opts a
            # session into "replay the covered prefix, execute the rest",
            # which is additive: every other replay session in the tree still
            # raises here (see ReplaySession.__init__).
            result, parent_hashes, started_at = await self._dispatch_with_timing(
                knot, inputs, gate, ticket_holder
            )
            return result, parent_hashes, started_at, False

        if isinstance(knot, Parameter):
            result, parent_hashes, started_at = await self._dispatch_with_timing(
                knot, inputs, gate, ticket_holder
            )
            if isinstance(result, Ok):
                replay.verify_executed(
                    knot_id=knot.knot_id,
                    output_hash=ContentHasher.hash(result.value),
                )
            return result, parent_hashes, started_at, False

        parent_hashes = {name: ContentHasher.hash(value) for name, value in inputs.items()}
        started_at = datetime.now(UTC)
        result = await replay.resolve(
            knot=knot,
            knot_config_hash=LineageRecorder.config_hash(knot),
            parent_input_hashes=parent_hashes,
            data_store=data_store,
        )
        return result, parent_hashes, started_at, True

    async def _dispatch_with_timing(
        self,
        knot: Knot,
        inputs: dict[str, Any],
        gate: Admission,
        ticket_holder: AdmissionTicketHolder,
    ) -> tuple[Result[Any], dict[str, str], datetime]:
        """Wrap dispatch with timing and parent-hash capture.

        Returns ``(result, parent_input_hashes, started_at)``.  The hashes
        are computed before dispatch so they reflect what the knot
        actually consumed.

        The dispatch runs under the knot's ``timeout`` and ``retry`` policy
        (``GovernedDispatch``), which also releases and re-admits *this*
        knot's admission slot around a retry's backoff sleep (PIR-870) --
        ``gate`` and ``ticket_holder`` are threaded through for exactly that.
        ``started_at`` is the first attempt's start; under a retry policy the
        attempt count is stashed on the run-scoped knot for ``lineage_extra``
        to report as ``extra["attempts"]``.
        """
        # For RECEIVE_ERRORS knots the inputs may be Result objects; we
        # hash them as they are (they're already canonicalisable).  For
        # other policies inputs are raw values.
        parent_hashes = {name: ContentHasher.hash(value) for name, value in inputs.items()}
        started_at = datetime.now(UTC)
        result, attempts = await self._governed.dispatch(
            knot, inputs, gate=gate, ticket_holder=ticket_holder
        )
        if knot.config.retry is not None:
            knot.record_dispatch_extra({"attempts": attempts})
        return result, parent_hashes, started_at

    def _rebind_err(
        self,
        result: Result[Any],
        knot_id: str,
        ctx: RunContext,
    ) -> Result[Any]:
        """Re-register a placeholder ExceptionRecord with the live manager."""
        if isinstance(result, Err):
            placeholder = result.record
            rebindable = RebindableError(
                exc_type=placeholder.exc_type,
                message=placeholder.message,
                traceback_text=placeholder.traceback_text,
            )
            real = ctx.exceptions.record(knot_id, rebindable)
            return Err(record=real)
        return result
