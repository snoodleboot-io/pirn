"""Mirrored tests for the S5 durable multi-turn thread persistence (PIR-369)."""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.context.context_assembler import ContextAssembler
from pirn_agents.context.heuristic_token_estimator import HeuristicTokenEstimator
from pirn_agents.context.token_counter import TokenCounter
from pirn_agents.sessions.conversation_thread import ConversationThread
from pirn_agents.sessions.thread_context_builder import ThreadContextBuilder
from pirn_agents.sessions.thread_repository import ThreadRepository
from tests.sessions.conftest import DictMemoryStore, make_thread


class TestConversationThread:
    def test_append_auto_indexes_and_is_immutable(self) -> None:
        thread = ConversationThread(session_id="s1")
        extended = thread.append(role="user", content="hi").append(role="assistant", content="yo")
        assert len(thread.turns) == 0
        assert [t.index for t in extended.turns] == [0, 1]
        assert extended.turns[1].content == "yo"

    def test_round_trips_without_data_loss(self) -> None:
        thread = make_thread(session_id="s1", turns=("hi", "hello", "bye"))
        assert ConversationThread.from_payload(thread.to_payload()) == thread


class TestThreadRepository:
    async def test_save_then_load_round_trips(self) -> None:
        repo = ThreadRepository(store=DictMemoryStore())
        thread = make_thread(session_id="s1", turns=("hi", "hello"))
        await repo.save(thread)
        assert await repo.load("s1") == thread

    async def test_persists_across_process_restart(self) -> None:
        # A durable backend outlives any single repository instance: a fresh
        # ThreadRepository over the same store re-reads the thread, standing in
        # for the thread surviving a process restart.
        backend = DictMemoryStore()
        thread = make_thread(session_id="s1", turns=("turn-a", "turn-b", "turn-c"))
        await ThreadRepository(store=backend).save(thread)

        reopened = ThreadRepository(store=backend)
        restored = await reopened.load("s1")
        assert restored == thread

    async def test_load_missing_returns_none(self) -> None:
        repo = ThreadRepository(store=DictMemoryStore())
        assert await repo.load("ghost") is None

    async def test_delete_removes(self) -> None:
        repo = ThreadRepository(store=DictMemoryStore())
        await repo.save(make_thread(session_id="s1", turns=("hi",)))
        await repo.delete("s1")
        assert await repo.load("s1") is None

    async def test_rejects_non_thread(self) -> None:
        repo = ThreadRepository(store=DictMemoryStore())
        with pytest.raises(TypeError):
            await repo.save("bad")  # type: ignore[arg-type]


def _builder() -> ThreadContextBuilder:
    with Tapestry():
        return ThreadContextBuilder(
            thread=ConversationThread(session_id="s1"),
            _config=KnotConfig(id="tcb"),
        )


class TestThreadContextReconstruction:
    async def test_builds_ordered_context_items(self) -> None:
        thread = make_thread(session_id="s1", turns=("first", "second", "third"))
        items = await _builder().process(thread=thread)
        assert [i.position for i in items] == [0, 1, 2]
        assert items[0].content == "user: first"
        assert items[1].content == "assistant: second"

    async def test_resumed_thread_feeds_f17_assembler(self) -> None:
        # End-to-end F17 integration: a persisted thread is reloaded, rebuilt into
        # context items, and assembled under a token budget by the real
        # ContextAssembler — reconstructing the prior turns in order.
        backend = DictMemoryStore()
        thread = make_thread(session_id="s1", turns=("alpha", "beta", "gamma"))
        await ThreadRepository(store=backend).save(thread)

        resumed = await ThreadRepository(store=backend).load("s1")
        assert resumed is not None
        items = await _builder().process(thread=resumed)

        counter = TokenCounter(estimator=HeuristicTokenEstimator(), per_message_overhead=0)
        with Tapestry():
            assembler = ContextAssembler(
                items=items, budget=1000, counter=counter, _config=KnotConfig(id="asm")
            )
        assembled = await assembler.process(items=items, budget=1000, counter=counter)
        assert [i.content for i in assembled.kept] == [
            "user: alpha",
            "assistant: beta",
            "user: gamma",
        ]

    async def test_rejects_non_thread(self) -> None:
        with pytest.raises(TypeError):
            await _builder().process(thread="bad")  # type: ignore[arg-type]
