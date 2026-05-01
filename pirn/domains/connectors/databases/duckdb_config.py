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
        Per-connection DuckDB config (e.g. ``threads``, ``memory_limit``).
    """

    database: str | Path = ":memory:"
    read_only: bool = False
    config: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
