from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.sqlite._migrations import apply_migrations

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class SQLiteStore(TapestryStore):
    """TapestryStore backed by SQLite.

    Provide either an existing sqlite3.Connection or a file path; if a
    path is given the store opens its own connection lazily on first use.

    Live knot references are kept in-process; SQLite holds a snapshot of
    each knot (id, class, config, parent ids) for cross-process queries.

    **Transaction ownership.** :meth:`register` commits — or rolls back —
    exactly the transaction *its own statement* opened, and never touches one it
    found already open. This is the guarantee
    ``ColumnAwareSqlitePool.fetch_columns`` (PIR-801) and ``_SQLExecutor``
    (PIR-817) already make, and that ``SqlitePool`` takes up in PIR-819;
    ``sqlite3`` starts an implicit transaction for DML only, so comparing
    ``in_transaction`` before and after the statement identifies the owner
    precisely.

    Sampling the flag matters here because the connection is *designed* to be
    shared: :class:`~pirn.backends.sqlite.sqlite_history.SQLiteHistory`'s class
    docstring recommends passing one ``sqlite3.Connection`` to both, so a
    transaction opened by the history — or by the application itself — is
    documented usage. ``register`` previously committed unconditionally, which
    adopted whatever it found open, making someone else's half-written work
    durable and stealing their ability to roll it back (PIR-823).

    Reads (:meth:`snapshot`) open no transaction and so issue no ``COMMIT``,
    which matters beyond tidiness: under ``journal_mode=DELETE`` a ``COMMIT``
    must take the exclusive lock, so a concurrent reader would make a query that
    only read rows fail with ``database is locked``.

    One exception remains by design: :meth:`_ensure_init` runs the schema DDL
    through ``executescript``, which ``sqlite3`` documents as implicitly
    committing any pending transaction. Schema creation is one-time setup that
    must be durable for every later statement, so it is left unconditional —
    mirroring ``SqlitePool._open_connection``. Callers who hold a transaction
    across store calls should therefore let the store initialise first.
    """

    _schema_version_ddl = """
        CREATE TABLE IF NOT EXISTS pirn_schema_version (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL
        );
    """
    _store_ddl = """
        CREATE TABLE IF NOT EXISTS knots (
            knot_id TEXT PRIMARY KEY,
            knot_class TEXT NOT NULL,
            config_json TEXT NOT NULL,
            parents_json TEXT NOT NULL,
            registered_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_knots_class ON knots(knot_class);
    """
    _schema_version = 1

    def __init__(self, *, path: str = ":memory:", connection: Any = None) -> None:
        """Initialise the store.

        Args:
            path: File path for the SQLite database, or ``":memory:"`` for a
                transient in-process store.  Ignored when ``connection`` is
                provided.
            connection: An existing ``sqlite3.Connection`` to reuse.  Useful
                for sharing a single file between ``SQLiteStore`` and
                ``SQLiteHistory``.
        """
        import sqlite3

        self._path = path
        self._conn = connection or sqlite3.connect(path)
        self._live: dict[str, Knot] = {}
        self._initialized = False

    def _ensure_init(self) -> None:
        """Create schema tables and apply pending migrations on first call.

        Subsequent calls return immediately because ``_initialized`` is set
        to ``True`` after the first successful run.
        """
        if self._initialized:
            return
        self._conn.executescript(self._schema_version_ddl + self._store_ddl)
        apply_migrations(self._conn, "store", self._schema_version)
        self._conn.commit()
        self._initialized = True

    def register(self, knot: Knot) -> None:
        """Add a knot to the store.

        Persists the knot's id, class, config, and parent ids to the
        ``knots`` table.  If the same instance is registered again the row
        is replaced (idempotent).  Raises if a *different* instance carries
        the same knot id.

        Commits only the transaction this statement opened — see the class
        docstring for why that is not an unconditional commit.

        Args:
            knot: The knot to register.

        Raises:
            ValueError: If a different ``Knot`` instance with the same
                ``knot_id`` is already registered.
        """
        from datetime import UTC, datetime

        self._ensure_init()
        existing = self._live.get(knot.knot_id)
        if existing is not None and existing is not knot:
            raise ValueError(
                f"knot id {knot.knot_id!r} already registered with a different instance"
            )
        self._live[knot.knot_id] = knot

        config_json = knot.config.model_dump_json()
        parents_json = json.dumps({name: parent.knot_id for name, parent in knot.parents.items()})
        knot_class = f"{type(knot).__module__}.{type(knot).__qualname__}"
        now = datetime.now(UTC).isoformat()

        in_transaction_on_entry = bool(self._conn.in_transaction)
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO knots
                   (knot_id, knot_class, config_json, parents_json, registered_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (knot.knot_id, knot_class, config_json, parents_json, now),
            )
        except BaseException:
            if self._opened_transaction(self._conn, in_transaction_on_entry):
                self._conn.rollback()
            raise
        if self._opened_transaction(self._conn, in_transaction_on_entry):
            self._conn.commit()

    def get(self, knot_id: str) -> Knot | None:
        """Return the in-process ``Knot`` instance for ``knot_id``, or ``None``.

        Args:
            knot_id: Identifier of the knot to retrieve.

        Returns:
            The registered ``Knot`` instance, or ``None`` if not found.
        """
        return self._live.get(knot_id)

    def all(self) -> list[Knot]:
        """Return all registered knots held in memory.

        Returns:
            List of ``Knot`` instances in insertion order.
        """
        return list(self._live.values())

    def snapshot(self) -> TapestrySnapshot:
        """Return a snapshot ordered by ``registered_at`` from the database.

        Queries the ``knots`` table so that the snapshot reflects the
        persistent registration order rather than the in-process dict order.

        Returns:
            A frozen ``TapestrySnapshot`` with knot ids ordered by
            ``registered_at``.
        """
        self._ensure_init()
        cursor = self._conn.execute("SELECT knot_id FROM knots ORDER BY registered_at")
        return TapestrySnapshot(knot_ids=[row[0] for row in cursor.fetchall()])

    @staticmethod
    def _opened_transaction(connection: Any, in_transaction_on_entry: bool) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            connection: The ``sqlite3`` connection the statement ran on.
            in_transaction_on_entry: ``connection.in_transaction`` sampled before
                the statement ran.

        Returns:
            ``True`` only when a transaction is open now and none was open
            before, which makes this call its owner — and so the one responsible
            for ending it.
        """
        return bool(connection.in_transaction) and not in_transaction_on_entry

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Only call this when the store owns the connection (i.e. it was opened
        from a file path).  If a shared connection was injected at construction
        the caller is responsible for closing it.
        """
        self._conn.close()
