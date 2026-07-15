"""Deterministic stub doubles for the evaluation-harness tests.

These satisfy the provider interfaces the harness depends on without pulling in
any vendor SDK or embedding backend, so every test is backend-free and asserts
on exact, scripted output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

from pirn.core.providers.embedding_provider import EmbeddingProvider
from pirn.core.providers.llm_provider import LLMProvider


class ScriptedJudgeProvider(LLMProvider):
    """An :class:`LLMProvider` that replays a fixed list of reply strings.

    Each :meth:`chat` call returns the next scripted string as ``content`` and
    records the messages it was called with, so a test can drive per-claim /
    per-context judge verdicts deterministically and assert on the prompts.
    """

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
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
        if self._index < len(self._replies):
            text = self._replies[self._index]
            self._index += 1
        else:
            text = self._replies[-1] if self._replies else ""
        return {"role": "assistant", "content": text}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        reply = await self.chat(messages)

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"content": reply.get("content", "")}

        return _aiter()

    async def close(self) -> None:
        return None


class StubEmbeddingProvider(EmbeddingProvider):
    """An :class:`EmbeddingProvider` that maps text to a vector via a function."""

    def __init__(self, embed_fn: Callable[[str], Sequence[float]]) -> None:
        self._embed_fn = embed_fn
        self.embedded: list[list[str]] = []

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        self.embedded.append(list(texts))
        return [list(self._embed_fn(text)) for text in texts]

    async def close(self) -> None:
        return None


def bag_of_words_embedder(vocab: Sequence[str]) -> Callable[[str], list[float]]:
    """Return a deterministic term-presence embedder over ``vocab``."""

    def _embed(text: str) -> list[float]:
        tokens = set(text.lower().split())
        return [1.0 if word in tokens else 0.0 for word in vocab]

    return _embed
