"""Stub Service Bus message used by :class:`AzureServiceBusBroker`.

Provides a minimal stand-in for ``azure.servicebus.ServiceBusMessage`` so
unit tests with injected stub clients can exercise :meth:`publish` without
forcing the real Azure SDK import.
"""

from __future__ import annotations


class AzureServiceBusStubMessage:
    """Bytes-only message envelope mirroring SDK fields."""

    def __init__(
        self,
        *,
        body: bytes,
        key: bytes | None,
        headers: dict[str, bytes] | None,
    ) -> None:
        self.body = body
        self.session_id = key.decode("utf-8") if key is not None else None
        self.application_properties = (
            {name: bytes(val) for name, val in headers.items()} if headers else None
        )
