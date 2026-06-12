"""Configuration dataclass for :class:`MixpanelClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class MixpanelConfig(ConnectionConfig):
    """Configuration for a Mixpanel ingestion / Service-Account session.

    Attributes
    ----------
    project_token:
        Project token used by the ingestion SDK
        (``mixpanel.Mixpanel(token)``).
    api_secret:
        Legacy API secret (used by the older HTTP API surface).
    service_account_username / service_account_secret:
        Project service-account credentials for newer Mixpanel APIs.
    """

    project_token: str | None = None
    api_secret: str | None = None
    service_account_username: str | None = None
    service_account_secret: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "project_token",
        "api_secret",
        "service_account_secret",
    )
