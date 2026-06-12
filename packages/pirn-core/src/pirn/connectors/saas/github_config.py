"""Configuration dataclass for :class:`GitHubClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class GitHubConfig(ConnectionConfig):
    """Configuration for a GitHub REST/GraphQL session.

    Attributes
    ----------
    token:
        Personal access token or fine-grained access token used for
        token-based authentication.
    base_url:
        Root API URL — defaults to public GitHub. Override for GitHub
        Enterprise Server (e.g. ``https://github.example.com/api/v3``).
    app_id:
        GitHub App identifier — paired with ``private_key`` for App
        installation auth.
    private_key:
        PEM-encoded RSA private key for the GitHub App.
    """

    token: str | None = None
    base_url: str = "https://api.github.com"
    app_id: str | None = None
    private_key: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("token", "private_key")
