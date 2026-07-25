"""``Summarizer`` — the interface that compresses evicted context into a summary.

A summarizer turns the text of older, evicted context items into a single
compact string that stands in for them. It is provider-neutral: a concrete
implementation may call an LLM, apply an extractive heuristic, or defer to a
caller-supplied function. Tests inject a deterministic stub. The method is
async so an LLM-backed summarizer fits without changing the interface.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class Summarizer(PirnOpaqueValue):
    """Interface every context summarizer must satisfy."""

    async def summarize(self, contents: Sequence[str]) -> str:
        """Return a compact summary of the ordered ``contents``."""
        raise NotImplementedError(f"{type(self).__name__} must implement summarize()")
