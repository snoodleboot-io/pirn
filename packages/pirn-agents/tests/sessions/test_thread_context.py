"""``ThreadContext`` / ``ThreadContextBuilder`` (PIR-874)."""

from __future__ import annotations

from pirn.core.knot_config import KnotConfig
from pirn.core.payload import Payload

from pirn_agents.sessions.thread_context import ThreadContext
from pirn_agents.sessions.thread_context_builder import ThreadContextBuilder
from pirn_agents.sessions.thread_context_frame import ThreadContextFrame
from tests.sessions.conftest import make_thread


async def _build(turns: tuple[str, ...]) -> ThreadContext:
    thread = make_thread(session_id="sess-9", turns=turns)
    builder = ThreadContextBuilder(thread=thread, _config=KnotConfig(id="b"))
    return await builder.process(thread=thread)


class TestThreadContextBuilder:
    async def test_returns_a_payload_with_the_items_as_data(self) -> None:
        ctx = await _build(("hi", "yo"))
        assert isinstance(ctx, Payload)
        assert [i.content for i in ctx.data] == ["user: hi", "assistant: yo"]
        assert [i.position for i in ctx.data] == [0, 1]

    async def test_frame_names_the_thread_and_item_count(self) -> None:
        ctx = await _build(("hi", "yo"))
        assert isinstance(ctx.metadata, ThreadContextFrame)
        assert ctx.metadata.session_id == "sess-9"
        assert ctx.metadata.item_count == 2

    async def test_empty_thread(self) -> None:
        ctx = await _build(())
        assert ctx.data == ()
        assert ctx.metadata.item_count == 0

    async def test_audit_dict_has_both_halves(self) -> None:
        audit = (await _build(("hi",)))._pirn_audit_dict()
        assert audit["session_id"] == "sess-9"
        assert audit["item_count"] == 1
        assert audit["items"][0]["content"] == "user: hi"

    async def test_equality_is_structural(self) -> None:
        assert await _build(("hi",)) == await _build(("hi",))
        assert await _build(("hi",)) != await _build(("hi", "yo"))
