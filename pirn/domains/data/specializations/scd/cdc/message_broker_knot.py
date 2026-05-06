"""``MessageBrokerKnot`` — vending Knot for :class:`MessageBrokerConnection`.

A :class:`~pirn.domains.connectors.message_broker.MessageBroker` is a live,
stateful object holding open connections to an external messaging system.
It cannot travel through the pirn graph as a plain constructor argument
(R6 violation). This vending Knot receives a constructed broker instance
during ``process()`` and returns it wrapped in a pydantic-opaque
:class:`MessageBrokerConnection` so that consumer Knots can declare it as
a typed upstream dependency.

Share a single :class:`MessageBrokerKnot` across all Knots that need to
operate on the same broker connection.

Algorithm:
    1. Receive the caller-supplied :class:`MessageBroker` instance (any
       concrete broker satisfying the publish/consume interface).
    2. Wrap it in :class:`MessageBrokerConnection` for pydantic compatibility.
    3. Return the wrapper so downstream Knots receive it as a resolved value.

References:
    [1] pirn MessageBroker interface:
        pirn/domains/connectors/message_broker.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.data.specializations.scd.cdc.message_broker_connection import (
    MessageBrokerConnection,
)


class MessageBrokerKnot(Knot):
    """Construct and vend a :class:`MessageBrokerConnection`.

    Pass a live :class:`MessageBroker` as ``broker``. Downstream Knots
    declare this Knot as a typed ``__init__`` parameter and receive the
    :class:`MessageBrokerConnection` wrapper in ``process()``.
    """

    def __init__(self, *, broker: Knot | MessageBroker, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(broker=broker, _config=_config, **kwargs)

    async def process(self, *, broker: MessageBroker, **_: Any) -> MessageBrokerConnection:
        """Wrap the supplied broker in a :class:`MessageBrokerConnection`.

        Args:
            broker: A live :class:`MessageBroker` instance.

        Returns:
            A :class:`MessageBrokerConnection` wrapping the broker.
        """
        return MessageBrokerConnection(client=broker)
