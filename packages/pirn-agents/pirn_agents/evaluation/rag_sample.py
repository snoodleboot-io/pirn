"""``RagSample`` — the ``(query, contexts, answer)`` tuple RAG metrics score."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RagSample(PirnOpaqueValue):
    """One retrieval-augmented-generation exchange to evaluate.

    The common input to every RAG metric: the user ``query``, the ``contexts``
    the retriever returned, the generated ``answer``, and an optional
    ``ground_truth`` reference answer (required only by context recall).

    Attributes
    ----------
    query:
        The user question.
    contexts:
        Retrieved context passages, in retrieval rank order (rank matters for
        context precision).
    answer:
        The generated answer under evaluation.
    ground_truth:
        Optional gold reference answer; context recall needs it.
    """

    query: str
    contexts: tuple[str, ...] = ()
    answer: str = ""
    ground_truth: str | None = None

    def __post_init__(self) -> None:
        """Validate field types and normalise ``contexts`` to a ``tuple[str]``.

        Raises:
            TypeError: If ``query``/``answer`` are not strings, ``contexts`` is a
                bare ``str`` or contains a non-string, or ``ground_truth`` is
                neither a ``str`` nor ``None``.
        """
        if not isinstance(self.query, str):
            raise TypeError(f"RagSample.query must be a str, got {type(self.query).__name__}")
        if isinstance(self.contexts, str):
            raise TypeError("RagSample.contexts must be a sequence of str, not a single str")
        if not isinstance(self.contexts, Sequence):
            raise TypeError(
                f"RagSample.contexts must be a sequence, got {type(self.contexts).__name__}"
            )
        contexts = tuple(self.contexts)
        for index, ctx in enumerate(contexts):
            if not isinstance(ctx, str):
                raise TypeError(
                    f"RagSample.contexts[{index}] must be a str, got {type(ctx).__name__}"
                )
        object.__setattr__(self, "contexts", contexts)
        if not isinstance(self.answer, str):
            raise TypeError(f"RagSample.answer must be a str, got {type(self.answer).__name__}")
        if self.ground_truth is not None and not isinstance(self.ground_truth, str):
            raise TypeError(
                f"RagSample.ground_truth must be a str or None, "
                f"got {type(self.ground_truth).__name__}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "contexts": list(self.contexts),
            "answer": self.answer,
            "ground_truth": self.ground_truth,
        }
