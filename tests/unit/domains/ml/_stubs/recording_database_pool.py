"""Recording stub :class:`DatabaseConnectionPool` for tests."""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)


class RecordingDatabasePool(DatabaseConnectionPool):
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = list(rows) if rows is not None else []
        self.queries: list[tuple[str, tuple[Any, ...] | None]] = []
        self.closed: bool = False

    async def fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[Any]:
        self.queries.append((query, params))
        return list(self._rows)

    async def acquire(self) -> Any:
        return None

    async def release(self, connection: Any) -> None:
        return None

    async def close(self) -> None:
        self.closed = True
