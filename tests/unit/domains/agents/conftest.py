"""Shared stub doubles for the agent-domain core tests.

These doubles satisfy the public agent interfaces without pulling in a
vendor SDK. Each one is deterministic so the tests assert on exact
output shapes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.tool import Tool


class StubLLMProvider(LLMProvider):
    """Returns a scripted response on each :meth:`chat` call."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[list[Mapping[str, Any]]] = []

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append([dict(m) for m in messages])
        if self._index < len(self._responses):
            text = self._responses[self._index]
            self._index += 1
        else:
            text = self._responses[-1] if self._responses else ""
        return {"role": "assistant", "content": text}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        chunks = self._responses or [""]

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for chunk in chunks:
                yield {"content": chunk}

        return _aiter()

    async def close(self) -> None:
        return None


class StubMemoryStore(MemoryStore):
    """In-memory dict implementing :class:`MemoryStore`."""

    def __init__(self) -> None:
        self._data: dict[str, Mapping[str, Any]] = {}
        self.searched: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self._data[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self._data.get(key)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        self.searched.append(query)
        items = list(self._data.values())[:top_k]

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for item in items:
                yield item

        return _aiter()

    async def forget(self, key: str) -> None:
        self._data.pop(key, None)

    async def close(self) -> None:
        return None


class StubTool(Tool):
    """Tool double that records each invocation."""

    def __init__(
        self,
        *,
        name: str,
        description: str = "stub tool",
        handler: Callable[[Mapping[str, Any]], Any] | Any = "tool-result",
    ) -> None:
        self._name = name
        self._description = description
        self._handler = handler
        self.invocations: list[Mapping[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        self.invocations.append(dict(arguments))
        if callable(self._handler):
            return self._handler(arguments)
        return self._handler
