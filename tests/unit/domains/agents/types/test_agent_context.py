"""Unit tests for :class:`AgentContext`."""

from __future__ import annotations

from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage


class TestRoundtrip:
    def test_default_metadata_is_empty(self) -> None:
        ctx = AgentContext(messages=())
        assert ctx.messages == ()
        assert dict(ctx.metadata) == {}

    def test_construct_with_messages(self) -> None:
        m1 = AgentMessage(role="user", content="a")
        m2 = AgentMessage(role="assistant", content="b")
        ctx = AgentContext(messages=(m1, m2), metadata={"k": "v"})
        assert ctx.messages == (m1, m2)
        assert ctx.metadata["k"] == "v"

    def test_audit_dict_includes_messages_and_metadata(self) -> None:
        ctx = AgentContext(
            messages=(AgentMessage(role="user", content="x"),),
            metadata={"a": 1},
        )
        d = ctx._pirn_audit_dict()
        assert isinstance(d["messages"], list)
        assert d["messages"][0]["role"] == "user"
        assert d["metadata"] == {"a": 1}
