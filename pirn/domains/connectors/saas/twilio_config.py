"""Configuration dataclass for :class:`TwilioClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class TwilioConfig(ConnectionConfig):
    """Configuration for a Twilio REST API session.

    Attributes
    ----------
    account_sid:
        Twilio account SID — also used as the basic-auth username.
    auth_token:
        Auth token paired with ``account_sid``.
    region:
        Optional regional edge (e.g. ``ie1``, ``au1``); when ``None`` the
        default Twilio region is used.
    """

    account_sid: str | None = None
    auth_token: str | None = None
    region: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("auth_token",)
