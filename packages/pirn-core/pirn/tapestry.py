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

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn.backends.base.run_history import RunHistory
    from pirn.backends.base.tapestry_store import TapestryStore
    from pirn.core.identity.identity_resolver import IdentityResolver
    from pirn.core.knot import Knot
    from pirn.core.run_request import RunRequest
    from pirn.core.run_result import RunResult
    from pirn.core.transport.data_transport import DataTransport
    from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
    from pirn.engine.dispatchers.dispatcher import Dispatcher
    from pirn.recording.replay_session import ReplaySession


# ContextVar carrying the active tapestry inside a `with` block.  None when
# no tapestry context is active.  Async-safe because contextvars are
# task-local in asyncio.
_current_tapestry: ContextVar[Tapestry | None] = ContextVar("pirn_current_tapestry", default=None)

# ContextVar carrying the run_id of the currently-executing outer run.
# Set by Tapestry.run() so that SubTapestry._run_inner() can link inner
# runs to the correct outer run without requiring process() to know it.
_current_run_id: ContextVar[str | None] = ContextVar("pirn_current_run_id", default=None)

# ContextVar carrying the history of the currently-executing run.  Set by
# Tapestry.run() so that SubTapestry nodes constructed dynamically mid-run
# (outside any `with Tapestry():` block) can still inherit the outer history
# and record their inner runs to the same store.
_current_history: ContextVar[Any] = ContextVar("pirn_current_history", default=None)

#: The emitter list the enclosing run is fanning events to, and the policy that
#: run applies when one of them raises.  Inner runs read both so a knot executing
#: inside a SubTapestry body reaches the same emitters as one executing at the
#: top level.  History was already forwarded to inner runs and emitters were not,
#: so the two observability planes disagreed about the same execution: an inner
#: knot appeared in ``history.children_of(...)`` but produced no status, lineage
#: or run-result event at all.  See PIR-834.
#:
#: ``None`` means "no enclosing run".  That is deliberately distinct from an
#: enclosing run whose emitter list is empty — ``run(emitters=[])`` is an
#: explicit opt-out, and an inner run must honour it rather than falling back to
#: the construction-time capture.
_current_emitters: ContextVar[list[Any] | None] = ContextVar("pirn_current_emitters", default=None)
_current_emitter_error_policy: ContextVar[Any] = ContextVar(
    "pirn_current_emitter_error_policy", default=None
)

#: The data store the enclosing run is writing knot outputs into.  Inner runs
#: read this so a value produced inside a ``SubTapestry`` body lands in the same
#: store as the lineage row that references it.  History was already forwarded
#: to inner runs and the data store was not, so an inner ``KnotLineage`` row
#: recorded an ``output_hash`` that resolved against nothing: the record's
#: lineage half was durable and its value half was written to a throwaway
#: ``InMemoryDataStore`` discarded when the inner run ended.  See PIR-837.
#:
#: ``None`` means "no enclosing run"; the construction-time capture is then the
#: right answer.  Unlike ``_current_emitters`` there is no empty-but-meaningful
#: value to distinguish — a run always has exactly one data store.
_current_data_store: ContextVar[Any] = ContextVar("pirn_current_data_store", default=None)

#: The transport the enclosing run is moving values over.  Inner runs read this
#: so a pipeline configured with a disk- or object-store-backed transport keeps
#: that transport inside a ``SubTapestry`` body instead of silently dropping
#: back to ``InlineTransport`` — which would defeat the memory-pressure reason
#: the transport was chosen for, precisely where the bulk of the work often
#: lives.  Unlike the data store this yields to an inner tapestry that chose its
#: own transport; see ``_apply_inherited_value_plane``.  See PIR-837.
_current_transport: ContextVar[Any] = ContextVar("pirn_current_transport", default=None)

#: The traceback filter the enclosing run is using.  Inner runs read this so a
#: filter set once at the top covers the whole tree — without it, an exception
#: raised inside a SubTapestry is redacted in the outer record but stored
#: verbatim in the inner run's own record, which run history persists.
#: See PIR-725.
_current_traceback_filter: ContextVar[Any] = ContextVar(
    "pirn_current_traceback_filter", default=None
)

# ContextVar carrying the store of the currently-executing extensible run.
# Set only when extensible=True.  Knots can call get_current_store() during
# process() to register new knots into the running tapestry — the engine
# picks them up between waves.  None in non-extensible runs.
_current_store: ContextVar[TapestryStore | None] = ContextVar("pirn_current_store", default=None)


def get_current_store() -> TapestryStore | None:
    """Return the store of the currently-executing extensible tapestry run.

    Returns ``None`` when called outside an extensible run.  Use this inside
    a knot's ``process()`` to register successor knots into the running
    tapestry — the engine picks them up between waves.

    Registration is permanent: the knot stays in the tapestry after this
    run ends and later runs treat it as an ordinary member.  Give it an
    id that is unique across runs — re-registering a different instance
    under an id an earlier run already used raises (PIR-815).

    Example::

        store = get_current_store()
        if store is not None:
            store.register(NextKnot(data=self, _config=KnotConfig(id="next")))
    """
    return _current_store.get(None)


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
        to ``LocalDispatcher``.
    """

    def __init__(
        self,
        *,
        store: TapestryStore | None = None,
        history: RunHistory | None = None,
        data_store: Any = None,  # DataStore protocol; deferred import
        dispatcher: Dispatcher | None = None,
        emitters: list[Any] | None = None,
        emitter_error_policy: EmitterErrorPolicy | None = None,
        traceback_filter: Callable[[str], str] | None = None,
        transport: DataTransport | None = None,
        identity_resolver: IdentityResolver | None = None,
    ) -> None:
        # Defer imports to avoid a circular at module load time.
        from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory
        from pirn.backends.in_memory.in_memory_store import InMemoryStore
        from pirn.core.identity.chained_identity_resolver import ChainedIdentityResolver
        from pirn.core.identity.env_identity_resolver import EnvIdentityResolver
        from pirn.core.identity.os_identity_resolver import OsIdentityResolver
        from pirn.core.transport.inline_transport import InlineTransport
        from pirn.emitters.base import EmitterErrorPolicy as _EmitterErrorPolicy
        from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher

        self._store = store or InMemoryStore()
        self._history = history or InMemoryHistory()
        self._data_store = data_store or InMemoryDataStore()
        self._dispatcher = dispatcher or LocalDispatcher()
        self._emitters: list[Any] = list(emitters or [])
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
    def data_store(self) -> Any:
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

    # ------------------------------------------------------------- knot ops

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
        emitters: list[Any] | None = None,
        extensible: bool = False,
        emitter_error_policy: EmitterErrorPolicy | None = None,
        traceback_filter: Callable[[str], str] | None = None,
        replay: ReplaySession | None = None,
        _parent_run_id: str | None = None,
        _parent_knot_id: str | None = None,
    ) -> RunResult:
        """Execute the tapestry against a ``RunRequest``.

        If ``terminals`` is omitted, all leaves of the tapestry are run.
        If ``dispatcher`` is omitted, the tapestry's default dispatcher is
        used.  If ``emitters`` is omitted, the tapestry's default
        emitters (set via the constructor or ``add_emitter``) are used;
        passing ``emitters=[]`` explicitly disables them for this run.

        Set ``extensible=True`` to enable mid-run extension: knots
        registered with the tapestry while the run is in flight are
        merged into the shed at the end of each wave.  Requires a
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

        Replay is not propagated into ``SubTapestry`` inner runs, and does
        not need to be: the ``SubTapestry`` knot itself is replayed from the
        outer recording, so the inner pipeline never starts.
        """
        from pirn.core.knot import Knot as _Knot
        from pirn.core.run_request import RunRequest as _RunRequest
        from pirn.engine.engine import Engine

        request = request or _RunRequest()

        # WHO resolution: explicit RunRequest.actor wins; fall back to resolver.
        resolved_actor = (
            request.actor if request.actor is not None else self._identity_resolver.resolve()
        )

        if terminals is None:
            chosen = self.terminals()
        elif isinstance(terminals, _Knot):
            chosen = [terminals]
        else:
            chosen = list(terminals)

        if not chosen:
            raise ValueError(
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

        engine = Engine(dispatcher=dispatcher or self._dispatcher)
        token_run_id = _current_run_id.set(request.run_id)
        token_store = _current_store.set(self._store if extensible else None)
        token_history = _current_history.set(self._history)
        # The value plane travels with the history: the store holds the value a
        # lineage row's output_hash names, so publishing one without the other
        # is what left inner rows pointing at nothing (PIR-837).
        token_data_store = _current_data_store.set(self._data_store)
        token_transport = _current_transport.set(self._transport)
        token_filter = _current_traceback_filter.set(active_filter)
        # Publish this run's emitter subscription so nested runs inherit it, the
        # same way they already inherit history and the traceback filter.
        token_emitters = _current_emitters.set(active_emitters)
        token_emitter_policy = _current_emitter_error_policy.set(active_policy)
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
                replay=replay,
            )
        finally:
            _current_run_id.reset(token_run_id)
            _current_store.reset(token_store)
            _current_history.reset(token_history)
            _current_data_store.reset(token_data_store)
            _current_transport.reset(token_transport)
            _current_traceback_filter.reset(token_filter)
            _current_emitters.reset(token_emitters)
            _current_emitter_error_policy.reset(token_emitter_policy)

    def add_emitter(self, emitter: Any) -> None:
        """Append an emitter to this tapestry's default emitter list.

        Subsequent ``run()`` calls will fan run events to this emitter
        unless overridden via ``run(emitters=...)``.
        """
        self._emitters.append(emitter)

    def remove_emitter(self, emitter: Any) -> None:
        """Remove an emitter by identity (not equality).

        Raises ``ValueError`` if the emitter is not registered.
        """
        for i, e in enumerate(self._emitters):
            if e is emitter:
                del self._emitters[i]
                return
        raise ValueError("emitter not registered with this tapestry")

    @property
    def emitters(self) -> list[Any]:
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

    # ----------------------------------------------------------- with-block

    def __enter__(self) -> Tapestry:
        # Set the ContextVar; remember the token so we can reset on exit.
        # If a tapestry is already active, we replace it for this block —
        # ContextVar.reset restores whatever was there before.
        self._token = _current_tapestry.set(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        token, self._token = self._token, None
        if token is not None:
            _current_tapestry.reset(token)

    def __repr__(self) -> str:
        return f"<Tapestry knots={len(self._store.all())}>"


def current_tapestry() -> Tapestry | None:
    """Return the tapestry active in the current `with` context, or None."""
    return _current_tapestry.get(None)


def current_run_id() -> str | None:
    """Return the run_id of the currently-executing run, or None.

    Downstream packages need run identity to correlate their own telemetry
    with the engine's lineage and status streams.  Without a public accessor
    they have to read the private ``_current_run_id``, so this exposes the
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
    return _current_run_id.get(None)


@contextmanager
def _run_id_scope(run_id: str | None) -> Iterator[None]:
    """Bind ``current_run_id()`` to ``run_id`` for the duration of the block.

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
    """
    token = _current_run_id.set(run_id)
    try:
        yield
    finally:
        _current_run_id.reset(token)
