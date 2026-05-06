"""``MessageBrokerConnection`` — pydantic-opaque wrapper for a :class:`~pirn.domains.connectors.message_broker.MessageBroker`.

A :class:`~pirn.domains.connectors.message_broker.MessageBroker` is a live,
stateful object holding open connections to an external messaging system.
This thin wrapper inherits
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` so it receives an
opaque ``isinstance`` schema, allowing it to travel between Knots in the
pirn graph without triggering pydantic schema generation errors.

The wrapped broker is accessed via the read-only :attr:`client` property.
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.connectors.message_broker import MessageBroker


class MessageBrokerConnection(PirnOpaqueValue):
    """Pydantic-opaque holder for a :class:`MessageBroker`.

    Pass this through the pirn graph and unwrap with ``.client`` in any
    consuming Knot's ``process()`` method.
    """

    def __init__(self, client: MessageBroker) -> None:
        self._client = client

    @property
    def client(self) -> MessageBroker:
        return self._client

    def _pirn_audit_dict(self) -> Any:
        return f"<MessageBrokerConnection@{id(self._client):x}>"
