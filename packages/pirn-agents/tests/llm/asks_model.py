"""``AsksModel`` — the knot the two-interpreter provider replay worker runs (PIR-840)."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from pirn_agents.llm.base_llm_provider import BaseLLMProvider


class AsksModel(Knot):
    """Holds a provider as a literal and returns the model's reply to one message."""

    def __init__(self, *, llm: BaseLLMProvider, **kwargs: Any) -> None:
        super().__init__(llm=llm, **kwargs)

    async def process(self, llm: BaseLLMProvider, **_: Any) -> str:
        reply = await llm.chat([{"role": "user", "content": "hello"}])
        return str(reply["content"])
