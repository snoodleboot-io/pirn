"""``SchemaVersionMigrator`` — applies versioned DDL migrations.

Reads migration records from a migration registry table, applies any
unapplied migrations in version order, and fails if a version gap is
detected.

Algorithm:
    1. Receive resolved ``pool``, ``migrations``, and ``migration_table``
       in ``process()``.
    2. Validate pool type, non-empty migrations list, version ordering,
       uniqueness, and positive version numbers.
    3. Fetch applied versions from ``migration_table``.
    4. Iterate migrations in order; skip already applied, fail on gaps.
    5. Execute each DDL and INSERT a tracking row into ``migration_table``.
    6. Return a summary dict with ``succeeded``, ``applied``, and ``skipped``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class SchemaVersionMigrator(Knot):
    """Apply versioned DDL migrations, tracking applied versions in a registry."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        migrations: Knot | Sequence[tuple[int, str]],
        migration_table: Knot | str = "schema_migrations",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            migrations=migrations,
            migration_table=migration_table,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        migrations: Any,
        migration_table: Any = "schema_migrations",
        **_: Any,
    ) -> dict[str, Any]:
        """Apply unapplied migrations in order, failing on version gaps.

        Args:
            pool: DatabaseConnectionPool to apply migrations against.
            migrations: Ordered sequence of (version, ddl) pairs; must be
                sorted ascending with no duplicates.
            migration_table: Registry table that tracks applied versions.

        Returns:
            A dict with keys ``succeeded``, ``applied``, and ``skipped``
            listing applied and skipped version numbers.

        Raises:
            TypeError: If ``pool`` is not a DatabaseConnectionPool.
            ValueError: If migrations are empty, unordered, duplicate, or a
                version gap is detected at runtime.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("SchemaVersionMigrator: pool must be a DatabaseConnectionPool")
        if not migrations:
            raise ValueError("SchemaVersionMigrator: migrations must be non-empty")
        mig_list = list(migrations)
        for idx, (version, ddl) in enumerate(mig_list):
            if not isinstance(version, int) or version < 1:
                raise ValueError(
                    f"SchemaVersionMigrator: migrations[{idx}] version must be a positive integer"
                )
            if not isinstance(ddl, str) or not ddl:
                raise ValueError(
                    f"SchemaVersionMigrator: migrations[{idx}] DDL must be a non-empty string"
                )
        IdentifierValidator.validate_column("migration_table", migration_table)
        versions = [v for v, _ in mig_list]
        sorted_versions = sorted(versions)
        if versions != sorted_versions:
            raise ValueError("SchemaVersionMigrator: migrations must be ordered by version")
        if len(set(versions)) != len(versions):
            raise ValueError("SchemaVersionMigrator: migration versions must be unique")

        rows = await pool.fetch_all(f"SELECT version FROM {migration_table}")
        applied_versions: set[int] = {row[0] for row in rows}
        applied = []
        skipped = []
        expected_next = (max(applied_versions) + 1) if applied_versions else 1
        for version, ddl in mig_list:
            if version in applied_versions:
                skipped.append(version)
                continue
            if version != expected_next:
                raise ValueError(
                    f"SchemaVersionMigrator: version gap detected — "
                    f"expected {expected_next}, got {version}"
                )
            await pool.execute(ddl)
            applied_at = datetime.now(UTC).isoformat()
            await pool.execute(
                f"INSERT INTO {migration_table} (version, applied_at) VALUES (?, ?)",
                (version, applied_at),
            )
            applied.append(version)
            expected_next = version + 1
        return {
            "succeeded": True,
            "applied": applied,
            "skipped": skipped,
        }
