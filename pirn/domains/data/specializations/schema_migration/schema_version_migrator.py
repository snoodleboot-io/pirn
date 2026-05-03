"""``SchemaVersionMigrator`` — applies versioned DDL migrations.

Reads migration records from a migration registry table, applies any
unapplied migrations in version order, and fails if a version gap is
detected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class SchemaVersionMigrator(SubTapestry):
    """Apply versioned DDL migrations, tracking applied versions in a registry."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        migrations: Sequence[tuple[int, str]],
        migration_table: str = "schema_migrations",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "SchemaVersionMigrator: pool must be a DatabaseConnectionPool"
            )
        if not migrations:
            raise ValueError(
                "SchemaVersionMigrator: migrations must be non-empty"
            )
        for idx, (version, ddl) in enumerate(migrations):
            if not isinstance(version, int) or version < 1:
                raise ValueError(
                    f"SchemaVersionMigrator: migrations[{idx}] version must be "
                    f"a positive integer"
                )
            if not isinstance(ddl, str) or not ddl:
                raise ValueError(
                    f"SchemaVersionMigrator: migrations[{idx}] DDL must be "
                    f"a non-empty string"
                )
        IdentifierValidator.validate_column(
            "migration_table", migration_table
        )
        versions = [v for v, _ in migrations]
        sorted_versions = sorted(versions)
        if versions != sorted_versions:
            raise ValueError(
                "SchemaVersionMigrator: migrations must be ordered by version"
            )
        if len(set(versions)) != len(versions):
            raise ValueError(
                "SchemaVersionMigrator: migration versions must be unique"
            )
        self._pool = pool
        self._migrations = list(migrations)
        self._migration_table = migration_table
        super().__init__(_config=_config, **kwargs)

    async def _get_applied_versions(self) -> set[int]:
        rows = await self._pool.fetch_all(
            f"SELECT version FROM {self._migration_table}"
        )
        return {row[0] for row in rows}

    async def process(self, **_: Any) -> dict[str, Any]:
        """Apply unapplied migrations in order, failing on version gaps.

        Migrations already recorded in the migration table are skipped.
        If a gap is detected between applied versions and the next migration,
        a ValueError is raised.

        Returns:
            A dict with keys ``succeeded``, ``applied``, and
            ``skipped`` listing applied and skipped version numbers.
        """
        applied_versions = await self._get_applied_versions()
        applied = []
        skipped = []
        expected_next = (max(applied_versions) + 1) if applied_versions else 1
        for version, ddl in self._migrations:
            if version in applied_versions:
                skipped.append(version)
                continue
            if version != expected_next:
                raise ValueError(
                    f"SchemaVersionMigrator: version gap detected — "
                    f"expected {expected_next}, got {version}"
                )
            await self._pool.execute(ddl)
            applied_at = datetime.now(timezone.utc).isoformat()
            await self._pool.execute(
                f"INSERT INTO {self._migration_table} (version, applied_at) "
                f"VALUES (?, ?)",
                (version, applied_at),
            )
            applied.append(version)
            expected_next = version + 1
        return {
            "succeeded": True,
            "applied": applied,
            "skipped": skipped,
        }
