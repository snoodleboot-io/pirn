"""Shared doubles + factories for the F27 memory-management tests.

Deterministic, backend-free stubs: a dict-backed :class:`RecordingMemoryStore`
that actually persists (so store/retrieve/forget round-trip), a scripted
:class:`StubSummarizer` standing in for the F17 summarizer seam, a
:class:`StubReranker` for the F4 rerank hook, and a :func:`make_record` factory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pirn_agents.context.summarizer import Summarizer
from pirn_agents.memory_management.memory_kind import MemoryKind
from pirn_agents.memory_management.memory_provenance import MemoryProvenance
from pirn_agents.memory_management.memory_record import MemoryRecord
from pirn_agents.memory_store import MemoryStore
from pirn_agents.rerank.reranker_backend import RerankerBackend


class RecordingMemoryStore(MemoryStore):
    """A dict-backed store that persists writes and records every call."""

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


class StubSummarizer(Summarizer):
    """Concatenates contents deterministically, standing in for the F17 seam."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def summarize(self, contents: Sequence[str]) -> str:
        self.calls.append(list(contents))
        return "SUMMARY(" + " | ".join(contents) + ")"


class StubReranker(RerankerBackend):
    """Scores documents by a scripted map from record id to score."""

    def __init__(self, scores_by_id: Mapping[str, float]) -> None:
        self._scores = dict(scores_by_id)
        self.calls: list[str] = []

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        self.calls.append(query)
        return [float(self._scores.get(str(doc.get("id")), 0.0)) for doc in documents]


def make_provenance(
    *,
    source: str = "test",
    timestamp: datetime | None = None,
    trust_signal: float = 1.0,
    derivation: str | None = None,
) -> MemoryProvenance:
    """Build a :class:`MemoryProvenance` with sensible test defaults."""
    return MemoryProvenance(
        source=source,
        timestamp=timestamp if timestamp is not None else datetime(2026, 1, 1, tzinfo=UTC),
        trust_signal=trust_signal,
        derivation=derivation,
    )


def make_record(
    *,
    id: str,
    kind: MemoryKind = "episodic",
    content: str = "content",
    importance: float = 0.0,
    created_at: datetime | None = None,
    last_accessed: datetime | None = None,
    trust_signal: float = 1.0,
    timestamp: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> MemoryRecord:
    """Build a :class:`MemoryRecord` with sensible test defaults."""
    created = created_at if created_at is not None else datetime(2026, 1, 1, tzinfo=UTC)
    return MemoryRecord(
        id=id,
        kind=kind,
        content=content,
        provenance=make_provenance(
            timestamp=timestamp if timestamp is not None else created,
            trust_signal=trust_signal,
        ),
        created_at=created,
        importance=importance,
        last_accessed=last_accessed,
        metadata=dict(metadata) if metadata is not None else {},
    )
