"""Unit tests for :class:`pirn_agents.llm.stream_delta.StreamDelta`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.stream_delta import StreamDelta


class TestStreamDelta(unittest.TestCase):
    def test_defaults_are_empty(self) -> None:
        delta = StreamDelta()
        assert delta.content == ""
        assert delta.tool_call is None
        assert delta.finish_reason is None
        assert delta.usage is None

    def test_audit_dict_copies_mappings(self) -> None:
        delta = StreamDelta(
            content="hi",
            tool_call={"index": 0, "arguments": "{}"},
            finish_reason="stop",
            usage={"output_tokens": 3},
        )
        audit = delta._pirn_audit_dict()
        assert audit == {
            "content": "hi",
            "tool_call": {"index": 0, "arguments": "{}"},
            "finish_reason": "stop",
            "usage": {"output_tokens": 3},
        }

    def test_audit_dict_handles_none(self) -> None:
        audit = StreamDelta(content="x")._pirn_audit_dict()
        assert audit["tool_call"] is None
        assert audit["usage"] is None


if __name__ == "__main__":
    unittest.main()
