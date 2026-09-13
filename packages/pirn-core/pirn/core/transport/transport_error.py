"""``TransportError`` — raised when a transport operation fails."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class TransportError(PirnError):
    """Raised by :class:`~pirn.core.transport.data_transport.DataTransport`
    implementations when a read, write, or cleanup operation cannot complete."""
