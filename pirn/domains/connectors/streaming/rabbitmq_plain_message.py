"""Plain-bytes message envelope used by :class:`RabbitMQBroker`.

Provides a minimal stand-in for ``aio_pika.Message`` so unit tests that
inject a stub channel can publish without forcing the real ``aio_pika``
import.
"""

from __future__ import annotations


class RabbitMQPlainMessage:
    """Bytes-only message envelope mirroring ``aio_pika.Message`` fields."""

    def __init__(
        self,
        *,
        body: bytes,
        key: bytes | None,
        headers: dict[str, bytes] | None,
    ) -> None:
        self.body = body
        self.correlation_id = key.decode("utf-8") if key is not None else None
        self.headers = headers
