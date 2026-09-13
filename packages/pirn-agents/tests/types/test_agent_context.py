"""Unit tests for the deprecated :class:`AgentContext` shim.

ADR agents-speaks-core WS6b renamed ``AgentContext`` to
:class:`~pirn_agents.types.messaging.conversation_payload.ConversationPayload`;
see ``test_conversation_payload.py`` for the real implementation's behaviour.
This file only pins the shim's two remaining jobs: staying importable and
constructible with the old signature, and warning that it is deprecated.
"""

from __future__ import annotations

import unittest
import warnings

from pirn_agents.types.messaging.agent_context import AgentContext
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_payload import ConversationPayload


class TestDeprecatedShim(unittest.TestCase):
    def test_construction_warns(self) -> None:
        # Not `self.assertWarns`: its `__enter__` clears `__warningregistry__`
        # on every module in `sys.modules` via `getattr`, which trips
        # `transformers`' lazy-module `__getattr__` into eagerly importing an
        # optional submodule (`torchvision`, not installed here) whenever a
        # heavy ML test earlier in the same session has already imported
        # `transformers`. A manual `catch_warnings` does not touch
        # `sys.modules` and sidesteps that interaction entirely.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            AgentContext(messages=())
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_is_a_conversation_payload(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx = AgentContext(messages=())
        assert isinstance(ctx, ConversationPayload)
        assert ctx.messages == ()

    def test_metadata_kwarg_becomes_extra(self) -> None:
        m1 = AgentMessage(role="user", content="a")
        m2 = AgentMessage(role="assistant", content="b")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx = AgentContext(messages=(m1, m2), metadata={"k": "v"})
        assert ctx.messages == (m1, m2)
        assert ctx.extra["k"] == "v"

    def test_audit_dict_includes_messages_and_extra(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx = AgentContext(
                messages=(AgentMessage(role="user", content="x"),),
                metadata={"a": 1},
            )
        d = ctx._pirn_audit_dict()
        assert isinstance(d["messages"], list)
        assert d["messages"][0]["role"] == "user"
        assert d["extra"] == {"a": 1}
