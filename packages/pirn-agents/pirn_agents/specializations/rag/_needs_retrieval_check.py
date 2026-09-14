"""``NeedsRetrievalCheck`` — should this sentence trigger a forward retrieval?

The ``Check`` (core role, ``pirn.nodes.check.Check``) behind the
:class:`~pirn.nodes.gate.gate.Gate` that keeps the retrieval + regeneration
calls from running when the generated sentence is already confident, or the
retrieval budget is spent (ADR agents-speaks-core WS5b).

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.check import Check

from pirn_agents.specializations.rag._flare_reply_parser import FlareReplyParser
from pirn_agents.specializations.rag.sentence_confidence_monitor import SentenceConfidenceMonitor


class NeedsRetrievalCheck(Check):
    """``True`` when the reply is low-confidence and the retrieval budget remains."""

    def __init__(
        self,
        *,
        reply: Knot | str,
        confidence_threshold: float,
        retrieval_calls_so_far: int,
        max_retrieval_calls: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            reply=reply,
            confidence_threshold=confidence_threshold,
            retrieval_calls_so_far=retrieval_calls_so_far,
            max_retrieval_calls=max_retrieval_calls,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        reply: str,
        confidence_threshold: float,
        retrieval_calls_so_far: int,
        max_retrieval_calls: int,
        **_: Any,
    ) -> bool:
        """Return whether ``reply``'s sentence should trigger a retrieval call.

        Args:
            reply: The raw generation reply.
            confidence_threshold: Confidence below which retrieval fires.
            retrieval_calls_so_far: Retrieval calls already spent this run.
            max_retrieval_calls: Hard cap on retrieval calls.

        Returns:
            ``False`` when the reply signals ``DONE``, the budget is spent,
            or the sentence is already confident; ``True`` otherwise.
        """
        if FlareReplyParser.is_done(reply):
            return False
        if retrieval_calls_so_far >= max_retrieval_calls:
            return False
        confidence, _sentence = FlareReplyParser.parse(reply)
        return SentenceConfidenceMonitor.needs_retrieval(confidence, confidence_threshold)
