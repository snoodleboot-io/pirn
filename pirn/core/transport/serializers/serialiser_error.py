"""``SerialiserError`` — raised when a serialiser cannot process a value."""

from __future__ import annotations


class SerialiserError(Exception):
    """Raised by :class:`~pirn.core.transport.serializers.serializer.Serializer`
    implementations when serialisation or deserialisation fails."""
