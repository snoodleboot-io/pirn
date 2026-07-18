"""``CrossEncoderReranker`` — a cross-encoder :class:`RerankerBackend`.

Scores ``(query, document)`` pairs with a `sentence-transformers` CrossEncoder
behind the ``[cross-encoder]`` extra. The model import is lazy so importing this
module stays backend-free, and the synchronous, CPU-bound ``predict`` call is
offloaded to a worker thread via :func:`asyncio.to_thread` so scoring never
blocks the event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.rerank.reranker_backend import RerankerBackend


class CrossEncoderReranker(RerankerBackend):
    """A cross-encoder relevance scorer implementing :class:`RerankerBackend`."""

    def __init__(
        self,
        *,
        model_name: str,
        text_key: str = "text",
        model_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the cross-encoder reranker.

        Args:
            model_name: Name/path of the cross-encoder model to load.
            text_key: Document mapping key holding the text to score; falls back
                to the whole mapping's string form when the key is absent.
            model_factory: Optional zero-arg factory returning a pre-built model
                exposing ``predict`` — the seam mirrored tests use to run offline
                without the extra installed.
        """
        self._model_name: str = model_name
        self._text_key: str = text_key
        self._model_factory: Callable[[], Any] | None = model_factory
        self._model: Any | None = None

    def _get_model(self) -> Any:
        """Return the model, factory-built or lazily loaded, once."""
        if self._model is None:
            if self._model_factory is not None:
                self._model = self._model_factory()
            else:
                sentence_transformers = _require("cross-encoder", "sentence_transformers")
                self._model = sentence_transformers.CrossEncoder(self._model_name)
        return self._model

    def _doc_text(self, document: Mapping[str, Any]) -> str:
        """Extract the scoreable text from a document mapping."""
        value = document.get(self._text_key)
        if isinstance(value, str):
            return value
        return " ".join(str(v) for v in document.values())

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        """Score every document against ``query`` on a worker thread.

        Args:
            query: The query to score relevance against.
            documents: The candidate documents.

        Returns:
            One float score per document, in input order.
        """
        if not documents:
            return []
        model = self._get_model()
        pairs = [[query, self._doc_text(document)] for document in documents]

        def _predict() -> Any:
            return model.predict(pairs)

        raw = await asyncio.to_thread(_predict)
        return [float(value) for value in raw]
