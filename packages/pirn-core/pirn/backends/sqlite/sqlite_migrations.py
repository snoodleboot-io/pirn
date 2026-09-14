from __future__ import annotations

from collections.abc import Callable
from typing import Any


class SqliteMigrations:
    """Versioned schema migrations recorded in ``pirn_schema_version``."""

    @staticmethod
    def apply(
        conn: Any,
        component: str,
        target: int,
        migrations: dict[int, Callable[[Any], None]] | None = None,
    ) -> None:
        """Advance the SQLite schema version for component from current to target.

        migrations maps version number -> migration function(conn).
        """
        migrations = migrations or {}
        row = conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component = ?",
            (component,),
        ).fetchone()
        current = row[0] if row else 0
        for v in range(current, target):
            fn = migrations.get(v + 1)
            if fn is not None:
                fn(conn)
        conn.execute(
            "INSERT OR REPLACE INTO pirn_schema_version (component, version) VALUES (?, ?)",
            (component, target),
        )
