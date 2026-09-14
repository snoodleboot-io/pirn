"""``AgentContext`` — deprecated; construct :class:`ConversationPayload` directly.

.. deprecated::
    ADR agents-speaks-core WS6b: ``AgentContext`` predated core's ``Payload``
    split and carried its conversation window as a flat frozen dataclass
    (``messages`` + a free-form ``metadata`` bag), colliding with core's own
    ``RunContext`` in name without sharing its shape (see
    ``agents-vocabulary-drift-20260913.md``'s glossary entry on "Context").
    :class:`~pirn_agents.types.messaging.conversation_payload.ConversationPayload`
    is ``Payload[ConversationFrame, tuple[AgentMessage, ...]]`` — the same two
    pieces of information (messages, free-form state), with the free-form bag
    renamed ``extra`` because ``Payload.metadata`` now names the frame. This
    name is kept importable for one deprecation cycle and raises a
    ``DeprecationWarning`` on construction.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_payload import ConversationPayload


class AgentContext(ConversationPayload):
    """Deprecated: construct :class:`ConversationPayload` directly."""

    def __init__(
        self,
        messages: Sequence[AgentMessage] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        warnings.warn(
            "AgentContext is deprecated (ADR agents-speaks-core WS6b); "
            "construct pirn_agents.types.messaging.conversation_payload."
            "ConversationPayload directly (its 'extra' kwarg replaces "
            "AgentContext's 'metadata').",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(messages, extra=metadata)

    # Note: pre-ADR call sites read the free-form bag as ``context.metadata``.
    # That name is now :attr:`Payload.metadata` (the frame) on every Payload
    # subclass, ``ConversationPayload`` included, so it cannot be shadowed
    # here without breaking Payload's own contract (Liskov: a property
    # override must not narrow its base type). Use :attr:`extra` instead —
    # the one call site and one test this repository had were both updated
    # in the same commit that introduced this shim.
