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

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn.backends import RunHistory, TapestryStore
    from pirn.core.context import RunRequest, RunResult
    from pirn.core.knot import Knot
    from pirn.engine.dispatcher import Dispatcher


# ContextVar carrying the active tapestry inside a `with` block.  None when
# no tapestry context is active.  Async-safe because contextvars are
# task-local in asyncio.
_CURRENT_TAPESTRY: ContextVar[Tapestry | None] = ContextVar(
    "pirn_current_tapestry", default=None
)


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
    ) -> None:
        # Defer imports to avoid a circular at module load time.
        from pirn.backends.in_memory import (
            InMemoryDataStore,
            InMemoryHistory,
            InMemoryStore,
        )
        from pirn.engine.dispatcher import LocalDispatcher

        self._store = store or InMemoryStore()
        self._history = history or InMemoryHistory()
        self._data_store = data_store or InMemoryDataStore()
        self._dispatcher = dispatcher or LocalDispatcher()
        self._emitters: list[Any] = list(emitters or [])

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
        from pirn.core.context import RunRequest as _RR
        from pirn.core.knot import Knot as _Knot
        from pirn.engine.engine import Engine

        request = request or _RR()

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

        active_emitters = (
            self._emitters if emitters is None else list(emitters)
        )

        engine = Engine(dispatcher=dispatcher or self._dispatcher)
        return await engine.execute(
            terminals=chosen,
            request=request,
            history=self._history,
            data_store=self._data_store,
            emitters=active_emitters,
            extensible_store=self._store if extensible else None,
        )

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
        self._token = _CURRENT_TAPESTRY.set(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        token, self._token = self._token, None
        if token is not None:
            _CURRENT_TAPESTRY.reset(token)

    def __repr__(self) -> str:
        return f"<Tapestry knots={len(self._store.all())}>"


def current_tapestry() -> Tapestry | None:
    """Return the tapestry active in the current `with` context, or None."""
    return _CURRENT_TAPESTRY.get(None)
