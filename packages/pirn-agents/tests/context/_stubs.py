"""Provider-neutral stub doubles shared by the context-layer tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.context.summarizer import Summarizer
from pirn_agents.context.token_estimator import TokenEstimator
from pirn_agents.memory_store import MemoryStore


class StubWordTokenEstimator(TokenEstimator):
    """A stub provider whose tokenization is one token per whitespace word.

    Distinct from the character heuristic so tests can prove the counter honours
    whichever provider strategy is injected.
    """

    def __init__(self, *, name: str = "stub-provider") -> None:
        self._name = name
        self.estimate_calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def estimate(self, text: str) -> int:
        self.estimate_calls.append(text)
        return len(text.split())


class StubSummarizer(Summarizer):
    """A deterministic summarizer that records what it was asked to compress."""

    def __init__(self, *, prefix: str = "SUMMARY") -> None:
        self._prefix = prefix
        self.summarize_calls: list[tuple[str, ...]] = []

    async def summarize(self, contents: Sequence[str]) -> str:
        recorded = tuple(contents)
        self.summarize_calls.append(recorded)
        return f"{self._prefix}[{len(recorded)}]"


class RecordingMemoryStore(MemoryStore):
    """An F27-style memory store that records every ``store`` call.

    Subclasses the real :class:`MemoryStore` interface (overriding only the
    write/read it needs) so it exercises the actual integration seam the
    compactor persists through.
    """

    def __init__(self) -> None:
        self.stored: list[tuple[str, dict[str, Any]]] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.stored.append((key, dict(value)))

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        for stored_key, value in reversed(self.stored):
            if stored_key == key:
                return value
        return None
