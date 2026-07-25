"""Shared backend-free doubles + factories for the F14 durable-session tests.

A dict-backed :class:`DictMemoryStore` that actually persists (so the persisted
adapters round-trip without any vendor backend), plus small factories for run
state and conversation threads.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn_agents.memory_store import MemoryStore
from pirn_agents.sessions.conversation_thread import ConversationThread
from pirn_agents.sessions.conversation_turn import ConversationTurn
from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_tool_result import SessionToolResult


class DictMemoryStore(MemoryStore):
    """A dict-backed :class:`MemoryStore` that persists writes and records calls."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}
        self.stored: list[str] = []
        self.forgotten: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.data[key] = dict(value)
        self.stored.append(key)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        found = self.data.get(key)
        return dict(found) if found is not None else None

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for value in list(self.data.values())[:top_k]:
                yield value

        return _aiter()

    async def forget(self, key: str) -> None:
        self.forgotten.append(key)
        self.data.pop(key, None)

    async def close(self) -> None:
        self.data.clear()


def make_run_state(
    *,
    session_id: str = "sess-1",
    messages: tuple[SessionMessage, ...] = (),
    plan: tuple[str, ...] = (),
    tool_results: tuple[SessionToolResult, ...] = (),
    step_index: int = 0,
) -> RunState:
    """Build a :class:`RunState` with sensible test defaults."""
    return RunState(
        session_id=session_id,
        messages=messages,
        plan=plan,
        tool_results=tool_results,
        cursor=ExecutionCursor(step_index=step_index, completed_steps=plan[:step_index]),
    )


def make_thread(*, session_id: str = "sess-1", turns: tuple[str, ...] = ()) -> ConversationThread:
    """Build a :class:`ConversationThread` whose turns alternate user/assistant."""
    built = tuple(
        ConversationTurn(
            index=i,
            role="user" if i % 2 == 0 else "assistant",
            content=text,
        )
        for i, text in enumerate(turns)
    )
    return ConversationThread(session_id=session_id, turns=built)
