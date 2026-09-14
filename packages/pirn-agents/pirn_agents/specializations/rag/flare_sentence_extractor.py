"""``FlareSentenceExtractor`` — pull the tentative sentence out of a generation reply.

Runs downstream of the ``Gate(input=generate, check=NeedsRetrievalCheck(...))``
in :class:`~pirn_agents.specializations.rag.flare_loop.FlareLoop`, so this
knot (and the retrieval + regeneration it feeds) is skipped along with the
gate whenever retrieval is not needed (ADR agents-speaks-core WS5b).

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.rag.flare_reply_parser import FlareReplyParser


class FlareSentenceExtractor(Knot):
    """Extract the tentative sentence text from a (gated) generation reply."""

    def __init__(
        self,
        *,
        reply: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(reply=reply, _config=_config, **kwargs)

    async def process(self, reply: str, **_: Any) -> str:
        """Return the tentative sentence parsed out of ``reply``.

        Args:
            reply: The (gated) raw generation reply.

        Returns:
            The tentative sentence text.
        """
        _confidence, sentence = FlareReplyParser.parse(reply)
        return sentence
