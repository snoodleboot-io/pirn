"""Shared stub doubles for agent specialization tests.

These doubles satisfy the public agent interfaces without bringing in a
vendor SDK. Each one is deterministic so the tests assert on exact
output shapes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.tools.tool import Tool
from pirn_agents.types.messaging.agent_response import AgentResponse


def response_sink(response: AgentResponse, knot_id: str) -> Knot:
    """Wrap ``response`` in a ``Source`` knot, as a ``SubTapestry`` sink must be.

    ``SubTapestry.process()`` is required to *return the sink knot* of the inner
    pipeline, not the answer itself — ``__call__`` then runs that pipeline and
    extracts the sink's output. Doubles that returned a bare ``AgentResponse``
    were violating the contract, and because the four multi-agent pipelines
    hand-called ``process()`` they never noticed. See PIR-769.

    Call this from inside a ``process()`` body so the knot auto-registers in the
    inner tapestry ``__call__`` has already opened.
    """

    class _ResponseSink(Source):
        async def process(self, **_: Any) -> AgentResponse:
            return response

    return _ResponseSink(_config=KnotConfig(id=knot_id))


class StubLLMProvider(LLMProvider):
    """Returns a script of canned responses on each :meth:`chat` call.

    By default the script is exhaustive: a call beyond the last scripted
    response raises. Replaying the last response forever hides bugs where a
    pipeline makes more calls than it should — it is how PIR-753's ReAct
    always-pay defect stayed invisible to every test. Pass
    ``repeat_last=True`` only where the call count is genuinely unbounded
    and not the property under test.
    """

    def __init__(self, responses: Sequence[str], *, repeat_last: bool = False) -> None:
        self._responses = list(responses)
        self._repeat_last = repeat_last
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
        elif self._repeat_last:
            text = self._responses[-1] if self._responses else ""
        else:
            raise AssertionError(
                f"StubLLMProvider: chat() call #{len(self.calls)} exceeds the "
                f"{len(self._responses)} scripted response(s). Either the code under "
                "test makes more LLM calls than intended, or this stub needs a longer "
                "script (or repeat_last=True if the count is genuinely unbounded)."
            )
        return {"role": "assistant", "content": text}

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        async def _aiter() -> AsyncIterator[StreamDelta]:
            yield StreamDelta(content="stub")

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
        return [float(((seed + offset) % 17) + 1) for offset in range(self._dimension)]


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
