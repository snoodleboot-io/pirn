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

Concurrency model: wave-based.  Each iteration finds all knots whose
parents are resolved and dispatches them concurrently via
``asyncio.gather``.  Simple, correct, easy to debug.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pirn.backends import DataStore, RunHistory
from pirn.core.config import ErrorPolicy
from pirn.core.context import RunContext, RunRequest, RunResult
from pirn.core.hashing import content_hash
from pirn.core.knot import Knot
from pirn.core.lineage import KnotLineage
from pirn.core.parameter import Parameter
from pirn.core.result import Err, Ok, Result, Skipped
from pirn.engine.dispatcher import Dispatcher, LocalDispatcher
from pirn.engine.shed import Shed
from pirn.managers.exceptions import RebindableException
from pirn.managers.status import KnotState


class Engine:
    """Async shed walker.  Owns no state across runs."""

    def __init__(self, dispatcher: Dispatcher | None = None) -> None:
        self._dispatcher = dispatcher or LocalDispatcher()

    async def execute(
        self,
        terminals: list[Knot],
        request: RunRequest,
        history: RunHistory,
        data_store: DataStore,
        emitters: list[Any] | None = None,
        extensible_store: Any = None,
    ) -> RunResult:
        shed = Shed.from_terminals(terminals)

        ctx = RunContext(
            run_id=request.run_id,
            terminals_requested=[t.knot_id for t in terminals],
            dispatcher_name=self._dispatcher.name,
            parameters=dict(request.parameters),
        )

        # Wire emitters' on_status to the StatusManager.  Async emitters
        # need to be invoked from a sync subscriber (StatusManager calls
        # subscribers synchronously); we schedule a task per event.
        emitters = emitters or []
        if emitters:
            self._subscribe_emitters_to_status(ctx, emitters)

        # Mid-run extension: subscribe to the store if one was provided.
        # New knots arriving during the run go into ``pending_new`` and
        # are merged into the shed between waves.
        pending_new: list[Knot] = []
        subscribe_token = None
        if extensible_store is not None:
            from pirn.backends.subscribe import SubscribableStore

            if not isinstance(extensible_store, SubscribableStore):
                raise TypeError(
                    "extensible_store must implement subscribe / unsubscribe; "
                    "the InMemoryStore is the reference implementation"
                )

            def _on_new_knot(knot: Knot) -> None:
                pending_new.append(knot)

            subscribe_token = extensible_store.subscribe(_on_new_knot)

        try:
            return await self._execute_loop(
                shed=shed,
                ctx=ctx,
                history=history,
                data_store=data_store,
                emitters=emitters,
                pending_new=pending_new,
                request=request,
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
        emitters: list[Any],
        pending_new: list[Knot],
        request: RunRequest,
    ) -> RunResult:

        # Bind parameters.  Setup-time errors propagate; recovery is the
        # caller's job (correct an unbound parameter and try again).
        self._bind_parameters(shed, ctx)

        # results[knot_id] holds Ok | Err | Skipped, or absent if not yet
        # considered.  We use the same dict for lineage I/O hash lookups.
        results: dict[str, Result[Any]] = {}

        order = shed.topological_order()
        remaining = set(order)

        while remaining:
            # Drain any knots registered mid-run before computing this
            # wave's ready set.  In extensible mode the store fires
            # subscribers as side-effects of register(); here we absorb
            # the queued knots into the shed (with race-checking) and
            # re-derive order / remaining so newcomers participate in
            # this wave or later.
            if pending_new:
                # Pop atomically; new registrations during merge land in
                # pending_new again and will be picked up next iteration.
                batch = list(pending_new)
                pending_new.clear()
                added = self._merge_new_knots(shed, batch, results, ctx)
                if added:
                    self._bind_parameters(shed, ctx)
                    order = shed.topological_order()
                    # Mark ids that completed already as not-remaining.
                    remaining = {kid for kid in order if kid not in results}

            ready = [
                kid
                for kid in order
                if kid in remaining and self._all_parents_resolved(shed, kid, results)
            ]
            if not ready:
                # Should never happen for a valid DAG.
                break

            tasks: dict[str, asyncio.Task[tuple[Result[Any], dict[str, str], datetime]]] = {}
            for kid in ready:
                knot = shed.knot(kid)
                ctx.status.transition(kid, KnotState.RUNNING)

                decision = self._decide(shed, knot, results, ctx)

                if isinstance(decision, Skipped):
                    results[kid] = decision
                    ctx.skipped.append(kid)
                    ctx.status.transition(kid, KnotState.SKIPPED, decision.reason)
                    self._record_lineage(ctx, knot, results, decision, started=ctx.started_at)
                    continue

                if isinstance(decision, Err):
                    # REQUIRE_ALL_PARENTS: synthetic Err.
                    results[kid] = decision
                    ctx.status.transition(kid, KnotState.FAILED, "missing parent")
                    self._record_lineage(ctx, knot, results, decision, started=ctx.started_at)
                    continue

                # decision is the resolved input dict.
                tasks[kid] = asyncio.create_task(self._dispatch_with_timing(knot, decision))

            for kid, task in tasks.items():
                result, parent_hashes, started_at = await task
                knot = shed.knot(kid)
                # Re-register placeholder records with the live manager.
                result = self._rebind_err(result, kid, ctx)
                results[kid] = result

                if isinstance(result, Ok):
                    ctx.status.transition(kid, KnotState.SUCCEEDED)
                    # Persist value to data store keyed by hash.
                    out_hash = content_hash(result.value)
                    await data_store.put(out_hash, result.value)
                elif isinstance(result, Skipped):
                    # A knot that runs but produces Skipped (e.g. a
                    # BranchOutput whose branch wasn't selected, a Gate
                    # that closed).  Recorded as skipped, not failed.
                    ctx.skipped.append(kid)
                    ctx.status.transition(kid, KnotState.SKIPPED, result.reason)
                else:
                    ctx.status.transition(kid, KnotState.FAILED)

                self._record_lineage(
                    ctx,
                    knot,
                    results,
                    result,
                    parent_hashes=parent_hashes,
                    started=started_at,
                )

            remaining -= set(ready)

            # Mid-run extension: pull any knots registered during this
            # wave and merge them into the shed for the next wave.  We
            # rebuild ``order`` to include the new knots in topological
            # position.  If a new knot depends on something that already
            # completed, that's a hard error — re-running the predecessor
            # would invalidate every consumer's input hash, which is too
            # costly to do silently.
            if pending_new:
                added_ids = self._merge_new_knots(
                    shed=shed,
                    new_knots=list(pending_new),
                    results=results,
                    ctx=ctx,
                )
                pending_new.clear()
                if added_ids:
                    # Re-bind parameters for any newly-arrived parameter
                    # knots.
                    self._bind_parameters(shed, ctx)
                    order = shed.topological_order()
                    remaining |= added_ids

        outputs = {kid: r.value for kid, r in results.items() if isinstance(r, Ok)}

        run_result = ctx.finalize(outputs)
        await history.record_run(run_result)

        # Fire emitter hooks for lineage and run result.  We do these
        # after history.record_run so emitters see the persisted state.
        # on_status was wired earlier as a subscriber to StatusManager.
        for emitter in emitters:
            for record in run_result.lineage:
                try:
                    await emitter.on_lineage(record)
                except Exception:
                    # Emitter failures must not break the run.  In Phase 4
                    # this routes through a structured logger; for now
                    # we swallow.
                    pass
            try:
                await emitter.on_run_result(run_result)
            except Exception:
                pass

        return run_result

    # ------------------------------------------------------------- helpers

    def _subscribe_emitters_to_status(
        self,
        ctx: RunContext,
        emitters: list[Any],
    ) -> None:
        """Subscribe each emitter's ``on_status`` to ``StatusManager``.

        StatusManager calls subscribers synchronously; emitters are
        async.  We schedule each call as a fire-and-forget task on the
        running loop.  Exceptions inside emitters are swallowed so a
        slow or broken emitter cannot break the run.
        """
        loop = asyncio.get_running_loop()
        # Strong-reference the in-flight tasks; without this, Python's
        # GC may reclaim them before they complete.  We attach to ctx
        # so the list lives as long as the run.
        if not hasattr(ctx, "_emitter_tasks"):
            ctx._emitter_tasks = []  # type: ignore[attr-defined]
        emitter_tasks: list[Any] = ctx._emitter_tasks  # type: ignore[attr-defined]

        def make_subscriber(emitter: Any):
            def subscriber(event):
                async def _wrapped():
                    try:
                        await emitter.on_status(event)
                    except Exception:
                        pass

                task = loop.create_task(_wrapped())
                emitter_tasks.append(task)
                # Drop completed tasks so the list doesn't grow unbounded.
                emitter_tasks[:] = [t for t in emitter_tasks if not t.done()]

            return subscriber

        for emitter in emitters:
            ctx.status.subscribe(make_subscriber(emitter))

    def _bind_parameters(self, shed: Shed, ctx: RunContext) -> None:
        for knot in shed.knots.values():
            if isinstance(knot, Parameter):
                if knot.name in ctx.parameters:
                    bound = knot.bind(ctx.parameters[knot.name])
                elif knot.has_default:
                    bound = knot.default
                else:
                    raise RuntimeError(
                        f"parameter {knot.name!r} has no value supplied and no default"
                    )
                knot.bind_value(bound)

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
        from pirn.engine.shed import Edge, ShedError

        added: set[str] = set()
        # First pass: filter to genuinely new knots.
        truly_new = [k for k in new_knots if k.knot_id not in shed.knots]
        if not truly_new:
            return added

        # Second pass: validate that no new knot depends on a knot that
        # already produced a result.  Walk recursively because a new
        # knot's parents may themselves be newly arrived.
        new_ids = {k.knot_id for k in truly_new}
        for k in truly_new:
            for parent in k.parents.values():
                if parent.knot_id in results:
                    raise ShedError(
                        f"knot {k.knot_id!r} arrived mid-run but its parent "
                        f"{parent.knot_id!r} has already completed; "
                        f"register dependent knots before their parents run"
                    )
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
        if shed._has_cycle():
            raise ShedError("cycle detected after mid-run merge")

        return added

    def _all_parents_resolved(self, shed: Shed, knot_id: str, results: dict[str, Any]) -> bool:
        for edge in shed.parents_of(knot_id):
            if edge.parent_id not in results:
                return False
        return True

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
            r = results[edge.parent_id]
            parent_results[edge.name] = r
            if isinstance(r, Skipped):
                any_skipped = True
            elif isinstance(r, Err):
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
                return Skipped(
                    reason="parent_failed_or_skipped",
                    detail={
                        "any_err": any_err,
                        "any_skipped": any_skipped,
                    },
                )
            # All parents are Ok at this point (we returned otherwise above).
            return {name: r.value for name, r in parent_results.items() if isinstance(r, Ok)}

        # RECEIVE_ERRORS: pass Result objects through unchanged.
        return dict(parent_results)

    async def _dispatch_with_timing(
        self,
        knot: Knot,
        inputs: dict[str, Any],
    ) -> tuple[Result[Any], dict[str, str], datetime]:
        """Wrap dispatch with timing and parent-hash capture.

        Returns ``(result, parent_input_hashes, started_at)``.  The hashes
        are computed before dispatch so they reflect what the knot
        actually consumed.
        """
        # For RECEIVE_ERRORS knots the inputs may be Result objects; we
        # hash them as they are (they're already canonicalisable).  For
        # other policies inputs are raw values.
        parent_hashes = {name: content_hash(value) for name, value in inputs.items()}
        started_at = datetime.now(UTC)
        result = await self._dispatcher.dispatch(knot, inputs)
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
            rebindable = RebindableException(
                exc_type=placeholder.exc_type,
                message=placeholder.message,
                traceback_text=placeholder.traceback_text,
            )
            real = ctx.exceptions.record(knot_id, rebindable)
            return Err(record=real)
        return result

    def _record_lineage(
        self,
        ctx: RunContext,
        knot: Knot,
        results: dict[str, Result[Any]],
        result: Result[Any],
        parent_hashes: dict[str, str] | None = None,
        started: datetime | None = None,
    ) -> None:
        """Build and stash a KnotLineage for this knot's execution.

        For knots that didn't actually dispatch (Skipped / synthetic Err),
        ``parent_hashes`` is computed here from the available parent
        results.
        """
        if parent_hashes is None:
            parent_hashes = {}
            # Recompute from the actual result map for knots that did
            # not dispatch (Skipped / synthetic Err).
            for parent_name, parent_knot in knot.parents.items():
                pr = results.get(parent_knot.knot_id)
                if pr is not None:
                    parent_hashes[parent_name] = content_hash(
                        pr.value if isinstance(pr, Ok) else pr
                    )

        if isinstance(result, Ok):
            outcome = "ok"
            output_hash = content_hash(result.value)
            error_record_id = None
            skip_reason = None
        elif isinstance(result, Err):
            outcome = "err"
            output_hash = None
            error_record_id = result.record.id
            skip_reason = None
        else:  # Skipped
            outcome = "skipped"
            output_hash = None
            error_record_id = None
            skip_reason = result.reason

        # If validate_io is on, we hash the canonical config (the user-
        # facing fields).  Otherwise we hash a sentinel.
        cfg_hash = content_hash(knot.config.model_dump(mode="json"))

        record = KnotLineage(
            run_id=ctx.run_id,
            knot_id=knot.knot_id,
            knot_class=f"{type(knot).__module__}.{type(knot).__qualname__}",
            knot_config_hash=cfg_hash,
            parent_input_hashes=parent_hashes,
            output_hash=output_hash,
            outcome=outcome,
            error_record_id=error_record_id,
            skip_reason=skip_reason,
            dispatcher=ctx.dispatcher_name,
            started_at=started or ctx.started_at,
            finished_at=datetime.now(UTC),
        )
        ctx.add_lineage(record)
