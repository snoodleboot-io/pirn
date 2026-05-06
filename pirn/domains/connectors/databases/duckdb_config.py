"""Configuration dataclass for :class:`DuckdbPool`."""

from __future__ import annotations

from dataclasses import field
from pathlib import Path
from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DuckdbConfig(ConnectionConfig):
    """Configuration for a DuckDB connection.

    Attributes
    ----------
    database:
        File path or ``":memory:"``.
    read_only:
        Open in read-only mode (forbids writes).
    config:
        Per-connection DuckDB config keys. Only safe, non-network-enabling
        keys are permitted (e.g. ``threads``, ``memory_limit``). Keys that
        enable external access or extension loading are rejected.
    """

    _allowed_duckdb_config_keys: ClassVar[frozenset[str]] = frozenset(
        {
            "threads",
            "memory_limit",
            "max_memory",
            "temp_directory",
            "default_order",
            "null_order",
            "checkpoint_threshold",
            "wal_autocheckpoint",
            "worker_threads",
            "external_threads",
            "access_mode",
            "log_query_path",
            "preserve_insertion_order",
            "arrow_large_buffer_size",
        }
    )

    database: str | Path = ":memory:"
    read_only: bool = False
    config: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    sensitive_fields: ClassVar[tuple[str, ...]] = ()

    def __post_init__(self) -> None:
        for index, (key, _value) in enumerate(self.config):
            if key not in self._allowed_duckdb_config_keys:
                raise ValueError(
                    f"DuckdbConfig: config[{index}] key {key!r} is not in the "
                    f"allowlist. Permitted keys: {sorted(self._allowed_duckdb_config_keys)}"
                )
