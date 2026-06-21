"""Record yielded by :class:`ValkeyStreamBroker.consume`.

Maps the field-map convention used by :class:`ValkeyStreamBroker` (``v`` →
value, ``k`` → key, ``h:<name>`` → header) onto the
:class:`MessageBroker`-compatible record surface
(``value`` / ``key`` / ``headers`` attributes).
"""

from __future__ import annotations


class ValkeyRecord:
    """One stream entry consumed via Valkey ``XREADGROUP``."""

    def __init__(
        self,
        *,
        entry_id: bytes,
        stream: str,
        fields: dict[bytes, bytes],
    ) -> None:
        self._entry_id = entry_id
        self._stream = stream
        self._fields = fields

    @property
    def id(self) -> bytes:
        return self._entry_id

    @property
    def stream(self) -> str:
        return self._stream

    @property
    def fields(self) -> dict[bytes, bytes]:
        return self._fields

    @property
    def value(self) -> bytes:
        return self._fields.get(b"v", b"")

    @property
    def key(self) -> bytes | None:
        return self._fields.get(b"k")

    @property
    def headers(self) -> dict[str, bytes]:
        return {
            k.removeprefix(b"h:").decode("utf-8"): v
            for k, v in self._fields.items()
            if k.startswith(b"h:")
        }
