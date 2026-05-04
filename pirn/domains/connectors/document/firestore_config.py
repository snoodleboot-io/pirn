"""Configuration dataclass for :class:`FirestorePool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class FirestoreConfig(ConnectionConfig):
    """Configuration for a Google Cloud Firestore async client.

    ``project_id`` is required and must be non-empty.
    """

    project_id: str = ""
    credentials_json: str | None = None
    database_id: str = "(default)"
    collection: str = ""

    sensitive_fields: ClassVar[tuple[str, ...]] = ("credentials_json",)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("FirestoreConfig: project_id must be non-empty")
