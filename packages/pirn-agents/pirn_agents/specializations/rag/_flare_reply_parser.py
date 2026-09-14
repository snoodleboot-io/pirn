"""``FlareReplyParser`` — parse a FLARE generation reply.

Shared by :class:`~pirn_agents.specializations.rag._needs_retrieval_check.NeedsRetrievalCheck`
and :class:`~pirn_agents.specializations.rag._flare_sentence_extractor.FlareSentenceExtractor`
so the ``CONF=<f>: <text>`` regex lives in one place.

Internal API. See PIR-856.
"""

from __future__ import annotations

import re


class FlareReplyParser:
    """Parse a FLARE generation reply into ``DONE``-ness or ``(confidence, sentence)``."""

    @staticmethod
    def is_done(reply: str) -> bool:
        """Return whether ``reply`` signals the answer is complete."""
        return reply.strip().upper().startswith("DONE")

    @staticmethod
    def parse(reply: str) -> tuple[float, str]:
        """Parse a ``CONF=<f>: <sentence>`` reply into ``(confidence, sentence)``.

        Args:
            reply: The raw generation reply.

        Returns:
            ``(confidence, sentence)``. A reply that does not match the
            expected shape is treated as maximally confident (``1.0``) with
            the whole reply as the sentence, so it never triggers retrieval.
        """
        match = re.match(r"\s*CONF\s*=\s*([01](?:\.\d+)?)\s*:\s*(.*)", reply, flags=re.DOTALL)
        if match is None:
            return 1.0, reply.strip()
        confidence = float(match.group(1))
        confidence = min(1.0, max(0.0, confidence))
        return confidence, match.group(2).strip()
