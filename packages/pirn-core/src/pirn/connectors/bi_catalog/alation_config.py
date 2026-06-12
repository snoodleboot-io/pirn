"""Configuration dataclass for :class:`AlationClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class AlationConfig(ConnectionConfig):
    """Configuration for the Alation REST API.

    Alation issues long-lived ``refresh_token`` strings to a specific
    ``user_id``; clients exchange the refresh token for short-lived
    access tokens. This connector sends the refresh token directly via
    Alation's ``Token`` header convention; richer flows can layer access
    tokens on top by overriding :meth:`request`.

    Attributes
    ----------
    base_url:
        Base URL of the Alation instance (e.g.
        ``https://alation.acme.com``).
    refresh_token:
        Refresh token issued by Alation.
    user_id:
        Numeric user ID associated with ``refresh_token``.
    """

    base_url: str | None = None
    refresh_token: str | None = None
    user_id: int | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("refresh_token",)
