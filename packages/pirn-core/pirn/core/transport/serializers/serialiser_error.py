"""``SerialiserError`` — raised when a serialiser cannot process a value."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class SerialiserError(PirnError):
    """Raised by :class:`~pirn.core.transport.serializers.serializer.Serializer`
    implementations when serialisation or deserialisation fails."""
