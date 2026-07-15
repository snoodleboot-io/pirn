"""``EgressError`` — an outbound request was refused by the egress policy.

Subclasses :class:`ValueError` so it drops straight into the F16
:class:`~pirn_agents.connectors.http_connector.HttpConnector` and the F6
``http_request`` tool, whose egress seams already document raising
:class:`ValueError` on a disallowed target — existing ``except ValueError``
handlers keep working unchanged.
"""

from __future__ import annotations


class EgressError(ValueError):
    """Raised when an egress policy blocks an outbound URL.

    Parameters
    ----------
    message:
        Human-readable reason for the block.
    host:
        The offending hostname, or ``None`` when it could not be parsed.
    """

    def __init__(self, message: str, *, host: str | None = None) -> None:
        self.host = host
        super().__init__(message)
