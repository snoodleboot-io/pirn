"""Configuration dataclass for :class:`LocalFilesystemStore`."""

from __future__ import annotations

from dataclasses import field
from pathlib import Path
from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class LocalFilesystemConfig(ConnectionConfig):
    """Configuration for the local-filesystem object store.

    Attributes
    ----------
    root:
        Base directory. Every key resolves strictly under this directory;
        keys that resolve outside (via ``..`` or absolute paths) are rejected.
    chunk_size:
        Streaming read chunk size in bytes.
    create_root:
        Create the root directory on first use when it does not exist.
    """

    root: Path = field(default_factory=Path)
    chunk_size: int = 1 << 20
    create_root: bool = True

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
