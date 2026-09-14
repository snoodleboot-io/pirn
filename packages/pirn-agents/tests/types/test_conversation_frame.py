"""Unit tests for :class:`ConversationFrame`."""

from __future__ import annotations

import unittest

from pirn_agents.types.messaging.conversation_frame import ConversationFrame


class TestRoundtrip(unittest.TestCase):
    def test_defaults(self) -> None:
        frame = ConversationFrame()
        assert frame.session_id is None
        assert frame.turn_id is None
        assert frame.token_count == 0
        assert frame.truncated is False
        assert dict(frame.extra) == {}

    def test_audit_dict(self) -> None:
        frame = ConversationFrame(
            session_id="s1", turn_id="t1", token_count=7, truncated=True, extra={"a": 1}
        )
        d = frame._pirn_audit_dict()
        assert d == {
            "session_id": "s1",
            "turn_id": "t1",
            "token_count": 7,
            "truncated": True,
            "extra": {"a": 1},
        }
