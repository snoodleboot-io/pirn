"""Unit tests for :class:`ConversationPayload`."""

from __future__ import annotations

import unittest

from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_frame import ConversationFrame
from pirn_agents.types.messaging.conversation_payload import ConversationPayload


class TestRoundtrip(unittest.TestCase):
    def test_default_frame_is_empty(self) -> None:
        payload = ConversationPayload(())
        assert payload.messages == ()
        assert dict(payload.extra) == {}
        assert payload.frame.session_id is None
        assert payload.frame.turn_id is None
        assert payload.frame.token_count == 0
        assert payload.frame.truncated is False

    def test_construct_with_messages_and_frame_fields(self) -> None:
        m1 = AgentMessage(role="user", content="a")
        m2 = AgentMessage(role="assistant", content="b")
        payload = ConversationPayload(
            (m1, m2),
            extra={"k": "v"},
            session_id="s1",
            turn_id="t1",
            token_count=42,
            truncated=True,
        )
        assert payload.messages == (m1, m2)
        assert payload.extra["k"] == "v"
        assert payload.frame == ConversationFrame(
            session_id="s1", turn_id="t1", token_count=42, truncated=True, extra={"k": "v"}
        )

    def test_metadata_is_the_frame_not_the_extra_bag(self) -> None:
        payload = ConversationPayload((), extra={"a": 1})
        assert payload.metadata is payload.frame
        assert isinstance(payload.metadata, ConversationFrame)

    def test_audit_dict_includes_messages_and_frame(self) -> None:
        payload = ConversationPayload(
            (AgentMessage(role="user", content="x"),),
            extra={"a": 1},
        )
        d = payload._pirn_audit_dict()
        assert isinstance(d["messages"], list)
        assert d["messages"][0]["role"] == "user"
        assert d["extra"] == {"a": 1}
        assert d["session_id"] is None

    def test_derive_inherits_frame_and_overrides(self) -> None:
        original = ConversationPayload(
            (AgentMessage(role="user", content="a"),),
            session_id="s1",
            token_count=10,
        )
        derived = original.derive(
            (AgentMessage(role="assistant", content="b"),), token_count=20
        )
        assert derived.messages[0].content == "b"
        assert derived.frame.session_id == "s1"
        assert derived.frame.token_count == 20
