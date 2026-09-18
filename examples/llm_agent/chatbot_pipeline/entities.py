"""``Entities`` — the named entities extracted from a turn.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entities:
    items: list[dict]  # [{"type": "PRODUCT", "value": "Pro plan"}, ...]
