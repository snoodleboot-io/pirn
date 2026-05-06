"""``MessageBrokerKnot`` — vending Knot for a :class:`MessageBroker`.

Wraps an externally-constructed broker so it participates in the pirn graph
with full lineage. Consumers receive the resolved broker value in their
``process()`` calls.

Algorithm:
    1. Accept the broker value (resolved by the framework from an upstream
       Knot or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the broker instance.


References:
    - :class:`pirn.domains.connectors.message_broker.MessageBroker`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.message_broker import MessageBroker


class MessageBrokerKnot(Knot):
    def __init__(self, *, broker: Knot | MessageBroker, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(broker=broker, _config=_config, **kwargs)

    async def process(self, broker: MessageBroker, **_: Any) -> MessageBroker:
        return broker
