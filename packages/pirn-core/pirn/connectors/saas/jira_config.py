"""Configuration dataclass for :class:`JiraClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class JiraConfig(ConnectionConfig):
    """Configuration for an Atlassian Jira session.

    Attributes
    ----------
    url:
        Base Jira URL (e.g. ``https://acme.atlassian.net``).
    username:
        Atlassian account email used as the basic-auth username.
    api_token:
        API token issued from the Atlassian account, paired with
        ``username``.
    cloud:
        ``True`` for Atlassian Cloud (default), ``False`` for an
        on-premise Jira Server / Data Center deployment.
    """

    url: str | None = None
    username: str | None = None
    api_token: str | None = None
    cloud: bool = True

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_token",)
