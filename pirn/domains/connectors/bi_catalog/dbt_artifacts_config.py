"""Configuration dataclass for :class:`DbtArtifactsReader`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DbtArtifactsConfig(ConnectionConfig):
    """Configuration for reading dbt artifacts off the local filesystem.

    Attributes
    ----------
    target_path:
        Filesystem path to dbt's ``target/`` directory containing
        ``manifest.json`` and ``run_results.json``.
    """

    target_path: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
