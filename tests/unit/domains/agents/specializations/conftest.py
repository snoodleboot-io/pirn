"""Shared stub doubles for agent specialization tests.

These doubles satisfy the public agent interfaces without bringing in a
vendor SDK. Each one is deterministic so the tests assert on exact
output shapes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.tool import Tool
from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.providers.embedding_provider import EmbeddingProvider


class StubLLMProvider(LLMProvider):
    """Returns a script of canned responses on each :meth:`chat` call."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[Sequence[Mapping[str, Any]]] = []

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append(list(messages))
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
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"content": "stub"}

        return _aiter()

    async def close(self) -> None:
        return None


class StubMemoryStore(MemoryStore):
    """Returns a fixed list of mappings from :meth:`search`."""

    def __init__(self, hits: Sequence[Mapping[str, Any]]) -> None:
        self._hits = [dict(hit) for hit in hits]
        self.search_queries: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        self.search_queries.append(query)

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for hit in self._hits[:top_k]:
                yield hit

        return _aiter()

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


class StubTool(Tool):
    """Returns a configured value from :meth:`invoke`.

    ``handler`` may be a plain return value or a callable applied to the
    incoming arguments mapping.
    """

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


class StubEmbeddingProvider(EmbeddingProvider):
    """Returns deterministic vectors derived from the input strings."""

    def __init__(
        self,
        *,
        dimension: int = 4,
        vectors: Sequence[Sequence[float]] | None = None,
    ) -> None:
        self._dimension = dimension
        self._scripted: list[list[float]] | None = (
            [list(vec) for vec in vectors] if vectors is not None else None
        )
        self._index = 0
        self.calls: list[list[str]] = []

    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._scripted is not None:
            out: list[list[float]] = []
            for _ in texts:
                if self._index >= len(self._scripted):
                    out.append(list(self._scripted[-1]))
                else:
                    out.append(list(self._scripted[self._index]))
                    self._index += 1
            return out
        return [self._derive(text) for text in texts]

    async def close(self) -> None:
        return None

    def _derive(self, text: str) -> list[float]:
        seed = sum(ord(ch) for ch in text)
        return [
            float(((seed + offset) % 17) + 1)
            for offset in range(self._dimension)
        ]


class StubDatabaseConnectionPool(DatabaseConnectionPool):
    """Records SQL queries and returns scripted rows."""

    def __init__(
        self,
        *,
        rows: Sequence[Any] = (),
    ) -> None:
        self._rows = list(rows)
        self.queries: list[str] = []

    async def acquire(self) -> Any:
        return None

    async def release(self, connection: Any) -> None:
        return None

    async def close(self) -> None:
        return None

    async def fetch_all(
        self,
        query: str,
        parameters: Any = None,
    ) -> list[Any]:
        self._reject_inline_interpolation(query)
        self.queries.append(query)
        return list(self._rows)
