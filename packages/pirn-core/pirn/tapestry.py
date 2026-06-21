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

from collections.abc import Callable
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
        protocol (``InMemoryStore`` does; the SQLite/Postgres/ValKey
        stores do not yet).
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

        active_emitters = self._emitters if emitters is None else list(emitters)
        active_policy = (
            emitter_error_policy if emitter_error_policy is not None else self._emitter_error_policy
        )
        active_filter = traceback_filter if traceback_filter is not None else self._traceback_filter

        engine = Engine(dispatcher=dispatcher or self._dispatcher)
        token_run_id = _current_run_id.set(request.run_id)
        token_store = _current_store.set(self._store if extensible else None)
        token_history = _current_history.set(self._history)
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
            )
        finally:
            _current_run_id.reset(token_run_id)
            _current_store.reset(token_store)
            _current_history.reset(token_history)

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
