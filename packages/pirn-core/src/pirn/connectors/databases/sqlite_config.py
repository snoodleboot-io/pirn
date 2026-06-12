"""Configuration dataclass for :class:`SqlitePool`."""

from __future__ import annotations

import re
from dataclasses import field
from pathlib import Path
from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


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
        for ``:memory:``. Must be one of DELETE, TRUNCATE, PERSIST, MEMORY,
        WAL, OFF.
    pragmas:
        Additional ``PRAGMA k=v`` settings applied at open time. Pragma
        names must match ``[a-z_]+`` to prevent injection.
    """

    _allowed_journal_modes: ClassVar[frozenset[str]] = frozenset(
        {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
    )
    _safe_pragma_name: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z_]+$")

    database: str | Path = ":memory:"
    timeout: float = 5.0
    journal_mode: str = "WAL"
    pragmas: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    sensitive_fields: ClassVar[tuple[str, ...]] = ()

    def __post_init__(self) -> None:
        if self.journal_mode.upper() not in self._allowed_journal_modes:
            raise ValueError(
                f"SqliteConfig: journal_mode {self.journal_mode!r} is not allowed. "
                f"Must be one of: {sorted(self._allowed_journal_modes)}"
            )
        for index, (name, _value) in enumerate(self.pragmas):
            if not self._safe_pragma_name.match(name):
                raise ValueError(
                    f"SqliteConfig: pragmas[{index}] name {name!r} contains "
                    "invalid characters. Only lowercase letters and underscores are allowed."
                )
