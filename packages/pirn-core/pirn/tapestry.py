"""Tapestry — the workspace where a pipeline lives.

A ``Tapestry`` is a container for the canonical set of knots that make up
a pipeline.  It is *backed* by a ``TapestryStore`` (in Phase 2: only
``InMemoryStore``); in Phase 3+ the same API works against SQLite,
DuckDB, Postgres, or ValKey backends without any user-code change.

Constructing knots inside a ``with Tapestry() as t:`` block auto-registers
them with that tapestry via a ``contextvars.ContextVar``.  Outside a
context, knots accept an explicit ``tapestry=`` kwarg.

The user-facing run entry point is ``tapestry.run(request)`` — the engine
is an internal collaborator, not something users construct directly.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pirn.core.run_context_vars import RunContextVars

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pirn.backends.base.data_store import DataStore
    from pirn.backends.base.run_history import RunHistory
    from pirn.backends.base.tapestry_store import TapestryStore
    from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
    from pirn.core.execution_plane import ExecutionPlane
    from pirn.core.identity.identity_resolver import IdentityResolver
    from pirn.core.knot import Knot
    from pirn.core.run_request import RunRequest
    from pirn.core.run_result import RunResult
    from pirn.core.transport.data_transport import DataTransport
    from pirn.emitters.emitter import Emitter
    from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
    from pirn.engine.admission.admission_observer import AdmissionObserver
    from pirn.engine.dispatchers.dispatcher import Dispatcher
    from pirn.recording.replay_session import ReplaySession


class Tapestry:
    """The workspace holding a set of knots and orchestrating their runs.

    Parameters
    ----------
    store:
        Where the canonical tapestry definition lives.  Defaults to
        ``InMemoryStore``.  Phase 3+ supports SQLite, Postgres, ValKey.
    history:
        Where lineage records and run results are stored.  Defaults to
        ``InMemoryHistory``.  Phase 3+ supports DuckDB, Postgres, etc.
    data_store:
        Where intermediate values (referenced by content hash) live.
        Defaults to ``InMemoryDataStore``.
    dispatcher:
        Default dispatcher used for runs that don't override it.  Defaults
        to ``LocalDispatcher``.  An inner tapestry (a ``SubTapestry`` body,
        a ``LoopSubTapestry`` iteration) that takes the default inherits the
        enclosing run's dispatcher instead; one given a dispatcher here
        keeps it (ADR agents-speaks-core, WS0b).
    concurrency:
        Default ``ConcurrencyLimits`` for runs whose ``RunRequest`` carries
        none: how many knots may be in flight at once, overall and per
        ``KnotConfig.concurrency_group``.  ``None`` (the default) is
        unbounded.  A request's own ``concurrency`` always wins.  An inner
        run that names no limits of its own -- neither here nor on its
        request -- shares the enclosing run's admission gate, the very same
        instance, so ``max_in_flight`` and every group cap are one budget
        across the whole run tree; an inner run that names a *bounded*
        budget of its own gets a gate chained under the enclosing run's, so
        admission takes a ticket from both and the tighter of the two
        always applies (PIR-870).  ``RunRequest(concurrency=ConcurrencyLimits())``
        -- explicitly unbounded -- is how a run opts out of the shared budget
        entirely: that gate is not chained, since chaining an
        always-admitting gate to the enclosing one would defeat the opt-out
        (WS0b).  The effective ceiling is also bounded by the dispatcher's
        own capacity, e.g. ``ThreadDispatcher(max_workers=...)``.
    max_nesting_depth:
        How many runs may be nested below a run of this tapestry, or
        ``None`` (the default) for no guard.  Every ``SubTapestry`` inner
        run, ``LoopSubTapestry`` loop run and loop iteration counts one
        level.  Setting it turns the nested-run guard on for the whole
        subtree: a run that would exceed the tightest cap on the path fails
        with ``NestingDepthExceededError``, and a container knot
        re-entering itself fails with ``NestedRunCycleError`` -- both
        recorded as the container knot's ``Err``.  An inner tapestry
        inherits the cap through the run context and may only tighten it.
    admission_observers:
        ``AdmissionObserver`` instances told of every admission and release in runs
        of this tapestry (queue depth, wait, hold time, outcome, and the
        gate itself so a limit can be adjusted in reaction).  A run's own
        ``admission_observers=`` replaces the list.  An inner run that
        shares the enclosing run's gate also hears its observers -- they
        belong to the gate they steer -- appended after the inner run's
        own and de-duplicated by identity (WS0b).
    identity_resolver:
        Resolves the actor recorded against a run whose ``RunRequest``
        carries none.  Defaults to the environment-then-OS chain.  An
        inner tapestry that takes the default inherits the enclosing run's
        resolver (WS0b).
    """

    def __init__(
        self,
        *,
        store: TapestryStore | None = None,
        history: RunHistory | None = None,
        data_store: DataStore | None = None,
        dispatcher: Dispatcher | None = None,
        emitters: list[Emitter] | None = None,
        emitter_error_policy: EmitterErrorPolicy | None = None,
        traceback_filter: Callable[[str], str] | None = None,
        transport: DataTransport | None = None,
        identity_resolver: IdentityResolver | None = None,
        concurrency: ConcurrencyLimits | None = None,
        max_nesting_depth: int | None = None,
        admission_observers: list[AdmissionObserver] | None = None,
    ) -> None:
        # Defer imports to avoid a circular at module load time.
        from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory
        from pirn.backends.in_memory.in_memory_store import InMemoryStore
        from pirn.core.identity.chained_identity_resolver import ChainedIdentityResolver
        from pirn.core.identity.env_identity_resolver import EnvIdentityResolver
        from pirn.core.identity.os_identity_resolver import OsIdentityResolver
        from pirn.core.transport.inline_transport import InlineTransport
        from pirn.emitters.emitter_error_policy import EmitterErrorPolicy as _EmitterErrorPolicy
        from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher

        self._store = store or InMemoryStore()
        self._history = history or InMemoryHistory()
        self._data_store = data_store or InMemoryDataStore()
        self._dispatcher = dispatcher or LocalDispatcher()
        # Whether the caller named this tapestry's dispatcher or took the
        # default.  An inner run inherits the enclosing run's dispatcher, but
        # must not overwrite one this tapestry was explicitly given -- same
        # reasoning as ``_transport_explicit`` below (WS0b).
        self._dispatcher_explicit: bool = dispatcher is not None
        self._emitters: list[Emitter] = list(emitters or [])
        self._emitter_error_policy: _EmitterErrorPolicy = (
            emitter_error_policy or _EmitterErrorPolicy.WARN
        )
        self._traceback_filter: Callable[[str], str] | None = traceback_filter
        self._transport: DataTransport = transport or InlineTransport()
        # Whether the caller named this tapestry's transport or took the
        # default.  An inner run inherits the enclosing run's transport, but
        # must not overwrite one this tapestry was explicitly given — a
        # ``LoopSubTapestry`` iteration built as ``Tapestry(transport=...)``
        # inside ``step()`` chose that transport for a reason.  The default
        # ``InlineTransport`` cannot be recognised by type: an outer run may
        # legitimately be inline too, and a concrete-type check would also
        # clobber an explicitly-passed ``InlineTransport``.  See PIR-837.
        self._transport_explicit: bool = transport is not None
        self._identity_resolver = identity_resolver or ChainedIdentityResolver(
            [EnvIdentityResolver(), OsIdentityResolver()]
        )
        # Same pattern: an inner run inherits the enclosing run's resolver
        # unless this tapestry was given one of its own (WS0b).
        self._identity_resolver_explicit: bool = identity_resolver is not None
        self._concurrency: ConcurrencyLimits | None = concurrency
        if max_nesting_depth is not None and (
            isinstance(max_nesting_depth, bool) or max_nesting_depth < 0
        ):
            raise ValueError(
                f"Tapestry: max_nesting_depth must be a non-negative int or None, "
                f"got {max_nesting_depth!r}"
            )
        self._max_nesting_depth: int | None = max_nesting_depth
        self._admission_observers: list[AdmissionObserver] = list(admission_observers or [])

        # Token returned by ContextVar.set, used to reset on __exit__.
        self._token: Any = None

    # --------------------------------------------------------------- access

    @property
    def store(self) -> TapestryStore:
        return self._store

    @property
    def history(self) -> RunHistory:
        return self._history

    @property
    def data_store(self) -> DataStore:
        return self._data_store

    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher

    @property
    def transport(self) -> DataTransport:
        return self._transport

    @property
    def identity_resolver(self) -> IdentityResolver:
        return self._identity_resolver

    @property
    def concurrency(self) -> ConcurrencyLimits | None:
        """Concurrency limits for runs whose ``RunRequest`` carries none."""
        return self._concurrency

    @property
    def max_nesting_depth(self) -> int | None:
        """Cap on nested runs below a run of this tapestry, or ``None`` for no guard."""
        return self._max_nesting_depth

    @property
    def admission_observers(self) -> list[AdmissionObserver]:
        """Read-only view of the default admission observers."""
        return list(self._admission_observers)

    # ------------------------------------------------------------- knot ops

    def adopt_history(self, history: RunHistory) -> None:
        """Record this tapestry's runs into *history*, an enclosing run's store.

        A container knot calls this on the inner tapestry it is about to run so
        inner runs land in the store the enclosing run is writing to and appear
        beside it in the explorer (PIR-764).

        Args:
            history: The enclosing run's history.
        """
        self._history = history

    def adopt_value_plane(
        self,
        *,
        data_store: DataStore | None,
        transport: DataTransport | None,
    ) -> None:
        """Point this tapestry at an enclosing run's value plane.

        The *value plane* is the pair a run writes its outputs into: the
        ``DataStore`` that holds each value by content hash, and the
        ``DataTransport`` that moves it between edges.  An inner tapestry is
        constructed with defaults, so without this its values go to a fresh
        ``InMemoryDataStore`` that is discarded the moment the inner run ends —
        while the inner *lineage* rows, written to the forwarded outer history, keep
        advertising ``output_hash`` values that now resolve against nothing
        (PIR-837).

        The two halves are not treated identically, because they are not the same
        kind of thing:

        * **The data store is forwarded unconditionally**, exactly as the history
          is.  A lineage row and the value it names are two halves of one record;
          routing the row to the outer history while routing the value elsewhere
          recreates the dangling reference this fixes.  Whoever owns the history
          owns the store that answers it.
        * **The transport yields to an inner tapestry that chose its own.**  A
          transport is a movement layer inside a single run, not part of any
          durable record: its handles never leave the run that created them and no
          lineage row references one.  Inheriting it keeps a disk- or object-store-
          backed pipeline from silently dropping to ``InlineTransport`` inside a
          ``SubTapestry`` body, which is where the bulk of a pipeline's data often
          moves.  But a ``LoopSubTapestry`` iteration built as
          ``Tapestry(transport=...)`` inside ``step()`` named that transport
          deliberately, and overwriting it would be the same silent override in the
          opposite direction.

        Sharing one transport instance across the outer and inner runs is safe:
        every ``DataTransport`` method is keyed by ``run_id``, and the inner run has
        its own, so ``begin_run`` / ``end_run`` allocate and release inner-run
        resources without touching the outer run's.  Sharing one data store is safe
        for a different reason: it is content-addressed, so an inner value that
        collides with an outer one is the same value.

        Args:
            data_store: The enclosing run's data store, or ``None`` when there is
                no enclosing run to inherit from.
            transport: The enclosing run's transport, or ``None`` likewise.
        """
        if data_store is not None:
            self._data_store = data_store
        if transport is not None and not self._transport_explicit:
            self._transport = transport

    def register(self, knot: Knot) -> None:
        """Add a knot to this tapestry.  Called automatically by ``Knot.__init__``
        when a tapestry context is active or an explicit ``tapestry=`` is
        passed.

        Idempotent in id: registering the same id twice with the same knot
        instance is a no-op; with a different instance it raises.
        """
        self._store.register(knot)

    def get(self, knot_id: str) -> Knot | None:
        return self._store.get(knot_id)

    def all_knots(self) -> list[Knot]:
        return self._store.all()

    def terminals(self) -> list[Knot]:
        """Knots that no other knot in this tapestry references as a parent.

        Computed on demand — the tapestry doesn't track this incrementally
        because splice operations would need to maintain it, and the cost
        of computing it is O(n) anyway.

        This reflects **every** member of the store, including knots a
        previous ``run(extensible=True)`` registered mid-run: such knots
        are permanent members of the tapestry, so a later ``run()`` that
        omits ``terminals=`` will execute them (PIR-815).  If you want a
        run confined to the statically-declared graph, pass ``terminals=``
        explicitly or use a fresh ``Tapestry``.
        """
        all_knots = self._store.all()
        referenced: set[str] = set()
        for k in all_knots:
            for parent in k.parents.values():
                referenced.add(parent.knot_id)
        return [k for k in all_knots if k.knot_id not in referenced]

    # -------------------------------------------------------------- run ops

    async def run(
        self,
        request: RunRequest | None = None,
        *,
        terminals: list[Knot] | Knot | None = None,
        dispatcher: Dispatcher | None = None,
        emitters: list[Emitter] | None = None,
        extensible: bool = False,
        emitter_error_policy: EmitterErrorPolicy | None = None,
        traceback_filter: Callable[[str], str] | None = None,
        replay: ReplaySession | None = None,
        admission_observers: list[AdmissionObserver] | None = None,
        _parent_run_id: str | None = None,
        _parent_knot_id: str | None = None,
        _nesting_key: str | None = None,
        _inner_run_ordinal: int | None = None,
    ) -> RunResult:
        """Execute the tapestry against a ``RunRequest``.

        If ``terminals`` is omitted, all leaves of the tapestry are run.
        If ``dispatcher`` is omitted, the tapestry's default dispatcher is
        used.  If ``emitters`` is omitted, the tapestry's default
        emitters (set via the constructor or ``add_emitter``) are used;
        passing ``emitters=[]`` explicitly disables them for this run.

        Set ``extensible=True`` to enable mid-run extension: knots
        registered with the tapestry while the run is in flight are
        merged into the shed each time a knot completes, and start as
        soon as their own parents have resolved.  Requires a
        ``TapestryStore`` that implements the ``SubscribableStore``
        protocol — ``InMemoryStore``, ``PostgresStore`` and
        ``ValKeyStore`` do; the SQLite store does not.  Only *this* run's
        own registrations are merged; a concurrent run's are not
        (PIR-808, PIR-815).

        ``extensible`` governs mid-run merging only.  Knots registered
        during an earlier run stay in the tapestry and are ordinary
        members afterwards, so a later run that omits ``terminals=``
        executes them whether or not it is extensible — see
        :meth:`terminals`.

        Pass ``replay=`` a ``ReplaySession`` to put the run in replay
        posture: every knot except ``Parameter`` is served its recorded
        outcome from that session and this tapestry's ``data_store``
        instead of being executed, so knots with side effects do not run.
        There is no matching record posture — recording is what an ordinary
        run already does.  A recording that cannot be honoured raises a
        ``ReplayError``; replay never silently falls back to executing.

        Replay posture is inherited by inner runs (ADR agents-speaks-core,
        WS0b).  In the ordinary case it is moot: the ``SubTapestry`` knot
        itself is served from the outer recording, so its inner pipeline
        never starts.  Should an inner run start while the enclosing run is
        in replay posture, it is served from the recording of the inner run
        the container's own recorded row names (``extra["inner_run_id"]``),
        loaded from this tapestry's history; a container with no recorded
        row runs its inner pipeline live.  A container that started several
        inner runs (``NestedRunKnot._run_inner`` called more than once) passes
        ``_inner_run_ordinal`` -- the run's index among them -- and is served
        from the recorded inner run at that index
        (``extra["inner_run_ids"]``).

        **Execution plane (WS0b).**  A run started inside another run --
        a ``SubTapestry`` body, a ``LoopSubTapestry`` iteration -- inherits
        the enclosing run's execution plane for everything it did not name
        itself: the dispatcher (unless this tapestry was given one), the
        admission gate and its ``ConcurrencyLimits`` (unless this request or
        tapestry names limits; the gate is shared *by identity*, so caps are
        one budget across the run tree), the admission observers (appended
        to this run's own when the gate is shared), the replay posture and
        the identity resolver.  Read the plane in force with
        :meth:`pirn.core.execution_plane.ExecutionPlane.current`.

        ``admission_observers`` replaces the tapestry's default observers for
        this run; ``None`` uses the defaults and ``[]`` silences this run's
        own -- inherited observers still hear a shared gate.

        ``_nesting_key`` is internal: a container knot starting this run as an
        inner run passes its nesting key (``SubTapestry._nesting_key``) so the
        nested-run guard can detect the container re-entering itself; a loop
        iteration passes none.  The run's frame is derived from the enclosing
        run's frame *before* anything starts, so a refused run raises here
        and never touches history.
        """
        from pirn.core.knot import Knot as _Knot
        from pirn.core.run_nesting import RunNesting as _RunNesting
        from pirn.core.run_request import RunRequest as _RunRequest
        from pirn.engine.engine import Engine
        from pirn.exceptions.tapestry_error import TapestryError

        request = request or _RunRequest()

        # Nested-run frame (WS0).  A root run starts its own frame; an inner
        # run derives its frame from the enclosing run's, which is where the
        # depth cap and the re-entry guard fire.
        enclosing = RunContextVars.nesting.get(None)
        enclosing_run_id = RunContextVars.run_id.get(None)
        if enclosing is None or enclosing_run_id is None:
            # A root run started by a container outside any engine run (a
            # SubTapestry awaited directly) still puts that container on
            # the path, so a re-entry below it is a cycle (ADR WS1).
            nesting = _RunNesting(
                path=(_nesting_key,) if _nesting_key is not None else (),
                max_depth=self._max_nesting_depth,
            )
        else:
            nesting = enclosing.child(
                _nesting_key, enclosing_run_id, max_depth=self._max_nesting_depth
            )

        # Execution plane (WS0b): what this run is scheduled on, metered by,
        # watched by, served from and attributed to -- inherited from the
        # enclosing run for everything this tapestry did not name itself.
        plane, limits_inherited = await self._resolve_execution_plane(
            request=request,
            dispatcher=dispatcher,
            admission_observers=admission_observers,
            replay=replay,
            parent_knot_id=_parent_knot_id,
            inner_run_ordinal=_inner_run_ordinal,
        )

        # WHO resolution: explicit RunRequest.actor wins; fall back to resolver.
        resolved_actor = (
            request.actor if request.actor is not None else plane.identity_resolver.resolve()
        )

        if terminals is None:
            chosen = self.terminals()
        elif isinstance(terminals, _Knot):
            chosen = [terminals]
        else:
            chosen = list(terminals)

        if not chosen:
            raise TapestryError(
                "tapestry has no knots / no terminals to run; construct knots "
                "inside `with Tapestry() as t:` or pass `terminals=`."
            )

        # Snapshot: the live list is mutable via add_emitter/remove_emitter,
        # and handing it to the run unwrapped let a subscription change made
        # while the run was in flight alter that run's emitter set mid-run.
        active_emitters = list(self._emitters) if emitters is None else list(emitters)
        active_policy = (
            emitter_error_policy if emitter_error_policy is not None else self._emitter_error_policy
        )
        active_filter = traceback_filter if traceback_filter is not None else self._traceback_filter

        engine = Engine(dispatcher=plane.dispatcher)
        token_run_id = RunContextVars.run_id.set(request.run_id)
        token_nesting = RunContextVars.nesting.set(nesting)
        token_plane = RunContextVars.execution_plane.set(plane)
        token_store = RunContextVars.store.set(self._store if extensible else None)
        token_history = RunContextVars.history.set(self._history)
        # The value plane travels with the history: the store holds the value a
        # lineage row's output_hash names, so publishing one without the other
        # is what left inner rows pointing at nothing (PIR-837).
        token_data_store = RunContextVars.data_store.set(self._data_store)
        token_transport = RunContextVars.transport.set(self._transport)
        token_filter = RunContextVars.traceback_filter.set(active_filter)
        # Publish this run's emitter subscription so nested runs inherit it, the
        # same way they already inherit history and the traceback filter.
        token_emitters = RunContextVars.emitters.set(active_emitters)
        token_emitter_policy = RunContextVars.emitter_error_policy.set(active_policy)
        try:
            return await engine.execute(
                terminals=chosen,
                request=request,
                history=self._history,
                data_store=self._data_store,
                emitters=active_emitters,
                extensible_store=self._store if extensible else None,
                traceback_filter=active_filter,
                emitter_error_policy=active_policy,
                parent_run_id=_parent_run_id,
                parent_knot_id=_parent_knot_id,
                transport=self._transport,
                actor=resolved_actor,
                replay=plane.replay,
                concurrency=plane.limits,
                nesting=nesting,
                admission_observers=list(plane.admission_observers),
                gate=plane.gate,
                limits_inherited=limits_inherited,
            )
        finally:
            RunContextVars.run_id.reset(token_run_id)
            RunContextVars.nesting.reset(token_nesting)
            RunContextVars.execution_plane.reset(token_plane)
            RunContextVars.store.reset(token_store)
            RunContextVars.history.reset(token_history)
            RunContextVars.data_store.reset(token_data_store)
            RunContextVars.transport.reset(token_transport)
            RunContextVars.traceback_filter.reset(token_filter)
            RunContextVars.emitters.reset(token_emitters)
            RunContextVars.emitter_error_policy.reset(token_emitter_policy)

    async def _resolve_execution_plane(
        self,
        *,
        request: RunRequest,
        dispatcher: Dispatcher | None,
        admission_observers: list[AdmissionObserver] | None,
        replay: ReplaySession | None,
        parent_knot_id: str | None,
        inner_run_ordinal: int | None = None,
    ) -> tuple[ExecutionPlane, bool]:
        """Resolve the plane a run of this tapestry executes under.

        See ``pirn.core.execution_plane`` for the algorithm.  Each half is
        resolved the same way: an explicit per-run argument wins, then this
        tapestry's own explicit setting, then the enclosing run's plane, then
        this tapestry's default.  The gate and the observers are decided
        together -- observers belong to the gate they steer, so an inner run
        that shares the outer gate also hears the outer observers, and one
        that builds its own gate hears only its own.

        Args:
            request: The run's request; its ``concurrency`` is the strongest
                limits setting.
            dispatcher: The ``run(dispatcher=)`` argument.
            admission_observers: The ``run(admission_observers=)`` argument.
            replay: The ``run(replay=)`` argument.
            parent_knot_id: The container knot starting this run, if any --
                what an inherited replay posture is keyed on.
            inner_run_ordinal: This run's index among the container's inner
                runs, when the container reported one.

        Returns:
            ``(plane, limits_inherited)``: the plane to publish, and whether
            its gate is the enclosing run's (so the engine skips the
            unused-group warning for limits declared for the whole tree).
        """
        from pirn.core.execution_plane import ExecutionPlane as _ExecutionPlane
        from pirn.engine.admission.chained_admission import ChainedAdmission
        from pirn.engine.engine import Engine

        enclosing = RunContextVars.execution_plane.get(None)
        own_limits = request.concurrency if request.concurrency is not None else self._concurrency

        if dispatcher is not None:
            active_dispatcher = dispatcher
        elif enclosing is not None and not self._dispatcher_explicit:
            active_dispatcher = enclosing.dispatcher
        else:
            active_dispatcher = self._dispatcher

        own_observers = (
            list(self._admission_observers)
            if admission_observers is None
            else list(admission_observers)
        )
        if enclosing is not None and own_limits is None:
            gate = enclosing.gate
            limits = enclosing.limits
            inherited = True
            observers = self._merged_observers(own_observers, enclosing.admission_observers)
        elif enclosing is not None and own_limits is not None and not own_limits.is_unbounded:
            # This run names its own *bounded* budget, but it still runs
            # inside the enclosing run's: chain the two gates so admission
            # takes a ticket from both and a slot held here is also a slot
            # the enclosing run's own budget cannot hand to anyone else
            # (PIR-870) -- rather than the two budgets being unrelated, as
            # they were before this fix. An explicitly *unbounded*
            # ``ConcurrencyLimits()`` stays the documented escape hatch
            # (falls to the branch below): it opts a run out of the shared
            # budget entirely, which chaining it to an always-admitting own
            # gate would defeat.
            gate = ChainedAdmission(own=Engine.gate_for(own_limits), parent=enclosing.gate)
            limits = own_limits
            inherited = False
            observers = own_observers
        else:
            gate = Engine.gate_for(own_limits)
            limits = own_limits
            inherited = False
            observers = own_observers

        if replay is None and enclosing is not None and enclosing.replay is not None:
            replay = await self._inherited_replay(
                enclosing.replay, parent_knot_id, inner_run_ordinal
            )

        if enclosing is not None and not self._identity_resolver_explicit:
            resolver = enclosing.identity_resolver
        else:
            resolver = self._identity_resolver

        plane = _ExecutionPlane(
            dispatcher=active_dispatcher,
            gate=gate,
            limits=limits,
            admission_observers=tuple(observers),
            replay=replay,
            identity_resolver=resolver,
        )
        return plane, inherited

    @staticmethod
    def _merged_observers(
        own: list[AdmissionObserver], inherited: tuple[AdmissionObserver, ...]
    ) -> list[AdmissionObserver]:
        """Combine a run's own observers with the enclosing run's, own first.

        De-duplicated by identity, like ``NestedRunKnot.inherited_emitters``:
        the same controller registered at both levels must hear each
        admission once.

        Args:
            own: This run's observers, in declared order.
            inherited: The enclosing plane's observers.

        Returns:
            The merged list.
        """
        merged = list(own)
        seen = {id(observer) for observer in merged}
        merged.extend(observer for observer in inherited if id(observer) not in seen)
        return merged

    async def _inherited_replay(
        self,
        outer: ReplaySession,
        parent_knot_id: str | None,
        inner_run_ordinal: int | None = None,
    ) -> ReplaySession | None:
        """Derive an inner run's replay session from the enclosing run's.

        The outer session indexes the *outer* run's knots; an inner run's
        knots are recorded in the inner run the container's lineage row
        names (``NestedRunKnot.lineage_extra`` → ``extra["inner_run_id"]``).
        A container that started several inner runs records all of them in
        start order (``extra["inner_run_ids"]``), and the run at
        *inner_run_ordinal* is served from the recording at that index.
        That recording is loaded from this tapestry's history, which
        ``NestedRunKnot._run_inner`` has already pointed at the outer store.
        The inner session keeps the outer session's ``allow_new_knots``, so a
        continuation that adds knots inside a container runs them live exactly
        as it does at the top level.

        Args:
            outer: The enclosing run's session.
            parent_knot_id: The container knot starting this run.
            inner_run_ordinal: This run's index among the container's inner
                runs, or ``None`` when the caller did not report one.

        Returns:
            A session over the recorded inner run, or ``None`` when the
            container has no recorded row, or its row names no inner run
            (a loop iteration, or a container that failed before recording
            one) -- the inner run then executes live, matching a session
            that lets the container itself execute live.

        Raises:
            ReplayMismatchError: If the row names an inner run the history
                no longer holds; replay never silently falls back to
                executing what it was told to serve.
        """
        from pirn.recording.replay_mismatch_error import ReplayMismatchError
        from pirn.recording.replay_session import ReplaySession as _ReplaySession

        if parent_knot_id is None:
            return None
        row = outer.row_for(parent_knot_id)
        if row is None:
            return None
        inner_run_id = self._recorded_inner_run_id(row.extra, inner_run_ordinal)
        if inner_run_id is None:
            return None
        try:
            return await _ReplaySession.from_history(
                history=self._history,
                run_id=inner_run_id,
                allow_new_knots=outer.allow_new_knots,
            )
        except KeyError as absent:
            raise ReplayMismatchError(
                knot_id=parent_knot_id,
                source_run_id=outer.source_run_id,
                reason=(
                    f"the container's recorded row names inner run {inner_run_id!r}, "
                    "which is no longer in history, so the inner pipeline cannot be replayed"
                ),
            ) from absent

    @staticmethod
    def _recorded_inner_run_id(extra: dict[str, Any], ordinal: int | None) -> str | None:
        """The recorded inner run a container's *ordinal*-th inner run replays.

        Args:
            extra: The container's recorded ``KnotLineage.extra``.
            ordinal: The inner run's index among the container's inner runs,
                or ``None`` when not reported.

        Returns:
            ``inner_run_ids[ordinal]`` when the row lists several inner runs;
            otherwise ``inner_run_id`` for the first (or an unreported) run;
            ``None`` when the row names no inner run at that index.
        """
        if ordinal is not None and "inner_run_ids" in extra:
            listed: Any = extra["inner_run_ids"]
            try:
                candidate: Any = listed[ordinal]
            except (IndexError, KeyError, TypeError):
                return None
            return candidate if isinstance(candidate, str) else None
        if ordinal not in (None, 0):
            return None
        single: object = extra.get("inner_run_id")
        return single if isinstance(single, str) else None

    def add_emitter(self, emitter: Emitter) -> None:
        """Append an emitter to this tapestry's default emitter list.

        Subsequent ``run()`` calls will fan run events to this emitter
        unless overridden via ``run(emitters=...)``.
        """
        self._emitters.append(emitter)

    def remove_emitter(self, emitter: Emitter) -> None:
        """Remove an emitter by identity (not equality).

        Raises ``TapestryError`` (a ``ValueError``) if the emitter is not
        registered.
        """
        from pirn.exceptions.tapestry_error import TapestryError

        for i, e in enumerate(self._emitters):
            if e is emitter:
                del self._emitters[i]
                return
        raise TapestryError("emitter not registered with this tapestry")

    @property
    def emitters(self) -> list[Emitter]:
        """Read-only view of the currently registered emitters."""
        return list(self._emitters)

    @property
    def emitter_error_policy(self) -> EmitterErrorPolicy:
        """How runs of this tapestry react when an emitter raises.

        Read-only companion to :attr:`emitters`.  ``SubTapestry`` reads it when
        capturing the outer subscription at construction time, so a forwarded
        emitter is governed by the policy its owner chose rather than silently
        reverting to the inner tapestry's default (PIR-834).
        """
        return self._emitter_error_policy

    @staticmethod
    def current_emitters() -> list[Emitter]:
        """Return the enclosing run's emitter list, or ``[]`` outside a run.

        Distinct from the instance property :attr:`emitters`: that is
        *this* tapestry's own registered list, read at construction/
        ``add_emitter`` time; this is the *ambient* run's subscription,
        read from the same contextvar :meth:`run` publishes for
        ``SubTapestry``/``LoopSubTapestry`` to inherit.

        Mirrors :meth:`current_run_id`: downstream packages that want to
        publish an ad hoc event through the run's own emitter subscription
        — an LLM call, a tool call, a retrieval step, none of which is a
        per-knot lifecycle transition the engine already reports — had no
        supported way to reach the run's emitters, only the private
        ``RunContextVars.emitters``. This exposes the same list under a
        supported name; see
        :meth:`pirn.engine.emitter_fanout.EmitterFanout.emit_status` for
        the sanctioned way to deliver an event to it.

        An empty list is returned both outside a run and when the
        enclosing run was itself given ``emitters=[]`` — an explicit
        opt-out that a caller reading this accessor must honour rather
        than falling back to some other source of emitters.
        """
        return list(RunContextVars.emitters.get(None) or [])

    @staticmethod
    def current_emitter_error_policy() -> EmitterErrorPolicy:
        """Return the enclosing run's emitter error policy.

        Defaults to
        :attr:`~pirn.emitters.emitter_error_policy.EmitterErrorPolicy.WARN`
        outside a run, matching :class:`Tapestry`'s own default, so a
        caller of :meth:`Tapestry.current_emitters` always has a sensible policy to
        pair it with.
        """
        from pirn.emitters.emitter_error_policy import EmitterErrorPolicy as _EmitterErrorPolicy

        policy = RunContextVars.emitter_error_policy.get(None)
        return policy if policy is not None else _EmitterErrorPolicy.WARN

    @staticmethod
    def current() -> Tapestry | None:
        """Return the tapestry active in the current `with` context, or None."""
        return RunContextVars.tapestry.get(None)

    @staticmethod
    def current_store() -> TapestryStore | None:
        """Return the store of the currently-executing extensible tapestry run.

        Returns ``None`` when called outside an extensible run.  Use this inside
        a knot's ``process()`` to register successor knots into the running
        tapestry — the engine merges them into the run when it processes the
        next knot completion, and a newcomer whose parents have all resolved
        starts straight away.

        Registration is permanent: the knot stays in the tapestry after this
        run ends and later runs treat it as an ordinary member.  Give it an
        id that is unique across runs — re-registering a different instance
        under an id an earlier run already used raises (PIR-815).

        Example::

            store = Tapestry.current_store()
            if store is not None:
                store.register(NextKnot(data=self, _config=KnotConfig(id="next")))
        """
        return RunContextVars.store.get(None)

    @staticmethod
    def current_run_id() -> str | None:
        """Return the run_id of the currently-executing run, or None.

        Downstream packages need run identity to correlate their own telemetry
        with the engine's lineage and status streams.  Without a public accessor
        they have to read the private ``RunContextVars.run_id``, so this exposes the
        same value under a supported name.

        Returns ``None`` outside a run, and ``None`` in an interpreter that never
        inherited the context — a process-boundary dispatcher (Ray/Dask/Celery)
        starts from an empty context, so callers there get nothing rather than a
        stale id.  It does survive a thread hop made with ``copy_context()``,
        which is how ``ThreadDispatcher`` hands off work (PIR-767).

        Inside a ``SubTapestry`` the value is the **inner** run's id, not the
        enclosing one: the inner ``Tapestry.run()`` sets the var for its own run
        and reads the outer value only to record it as ``parent_run_id``.

        There is deliberately no ``current_knot_id()`` companion.  Knot identity
        is never ambient — a knot reads ``self.knot_id``, and callers that are not
        knots must be told which knot they belong to.
        """
        return RunContextVars.run_id.get(None)

    async def close(self) -> None:
        """Close every registered emitter and the data store, releasing held resources.

        Called by the runtime when using ``async with Tapestry() as t:``
        (see :meth:`__aexit__`); callers of the plain synchronous
        ``with Tapestry() as t:`` form must await this explicitly, since a
        synchronous ``__exit__`` cannot await an emitter's async ``close()``.

        Each emitter is closed independently: one emitter raising does not
        stop the others from being closed, and every failure is logged at
        WARNING rather than propagated — mirroring the "must not raise"
        contract already documented on :meth:`Emitter.close`. The data store
        is closed last under the same isolation (:meth:`DataStore.close`);
        a store that holds a cloud client releases it here and reopens it
        lazily if the tapestry — or another one sharing the store — runs
        again (PIR-869).
        """
        for emitter in self._emitters:
            try:
                await emitter.close()
            except Exception:
                _logger.warning(
                    "Tapestry.close: emitter %r raised while closing", emitter.name, exc_info=True
                )
        try:
            await self._data_store.close()
        except Exception:
            _logger.warning(
                "Tapestry.close: data store %r raised while closing",
                type(self._data_store).__name__,
                exc_info=True,
            )

    @staticmethod
    @contextmanager
    def run_id_scope(run_id: str | None) -> Generator[None, None, None]:
        """Bind ``Tapestry.current_run_id()`` to ``run_id`` for the duration of the block.

        Internal.  ``Tapestry.run()`` owns run identity for real runs; this
        exists for the one case where a run's identity has to be *restored*
        rather than established — a durable store delivering a knot
        registration from a background LISTEN/pub-sub task that never
        inherited the registering task's context.  The store reads the
        registering run off the notification payload and rebinds it here so
        that everything downstream of ``subscribe()`` reads ambient run
        identity exactly as it does under ``InMemoryStore``, which delivers
        synchronously in the registering context (PIR-815).

        ``None`` is a legitimate value: it restores "no run in scope", which
        is what an unowned registration means.

        The block also runs with no dispatching knot in scope.  The
        notification does not say which knot registered, and the listener
        task's own context holds whatever knot happened to be executing when
        ``subscribe()`` started it -- for an inner run, a knot of the outer
        run -- which would otherwise be reported as the registrar (PIR-841).
        """
        token = RunContextVars.run_id.set(run_id)
        knot_token = RunContextVars.dispatching_knot_id.set(None)
        try:
            yield
        finally:
            RunContextVars.dispatching_knot_id.reset(knot_token)
            RunContextVars.run_id.reset(token)

    # ----------------------------------------------------------- with-block

    def __enter__(self) -> Tapestry:
        # Set the ContextVar; remember the token so we can reset on exit.
        # If a tapestry is already active, we replace it for this block —
        # ContextVar.reset restores whatever was there before.
        self._token = RunContextVars.tapestry.set(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        token, self._token = self._token, None
        if token is not None:
            RunContextVars.tapestry.reset(token)

    async def __aenter__(self) -> Tapestry:
        """Async form of :meth:`__enter__`; identical contextvar wiring."""
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async form of :meth:`__exit__` that also closes every emitter.

        Runs :meth:`close` before restoring the contextvar so a knot
        constructed from inside an emitter's ``close()`` (unusual, but not
        forbidden) still sees this tapestry as current.
        """
        try:
            await self.close()
        finally:
            self.__exit__(exc_type, exc_val, exc_tb)

    def __repr__(self) -> str:
        return f"<Tapestry knots={len(self._store.all())}>"
