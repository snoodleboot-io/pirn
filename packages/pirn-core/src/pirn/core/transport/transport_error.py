"""``TransportError`` — raised when a transport operation fails."""

from __future__ import annotations


class TransportError(Exception):
    """Raised by :class:`~pirn.core.transport.data_transport.DataTransport`
    implementations when a read, write, or cleanup operation cannot complete."""
