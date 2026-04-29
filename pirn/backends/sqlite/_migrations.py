from __future__ import annotations

from typing import Any


def apply_migrations(conn: Any, component: str, target: int) -> None:
    """Advance the SQLite schema version for component from current to target.

    Each step would call a migration function if one existed; right now
    v1 is the initial schema so no migration steps exist yet.
    """
    row = conn.execute(
        "SELECT version FROM pirn_schema_version WHERE component = ?",
        (component,),
    ).fetchone()
    current = row[0] if row else 0
    for _v in range(current, target):
        pass  # future: _migrate_v_to_{v+1}(conn)
    conn.execute(
        "INSERT OR REPLACE INTO pirn_schema_version (component, version) VALUES (?, ?)",
        (component, target),
    )
