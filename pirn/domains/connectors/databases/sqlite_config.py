"""Configuration dataclass for :class:`SqlitePool`."""

from __future__ import annotations

from dataclasses import field
from pathlib import Path
from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class SqliteConfig(ConnectionConfig):
    """Configuration for an async SQLite connection.

    Attributes
    ----------
    database:
        File path or ``":memory:"``.
    timeout:
        Lock-acquisition timeout in seconds.
    journal_mode:
        WAL is recommended for concurrent reads on disk databases; ignored
        for ``:memory:``.
    pragmas:
        Additional ``PRAGMA k=v`` settings applied at open time.
    """

    database: str | Path = ":memory:"
    timeout: float = 5.0
    journal_mode: str = "WAL"
    pragmas: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
