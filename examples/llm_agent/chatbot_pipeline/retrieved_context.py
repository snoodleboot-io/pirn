"""``RetrievedContext`` — the knowledge-base chunks the RAG stage returned.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievedContext:
    chunks: list[str]  # relevant knowledge-base excerpts
    source_ids: list[str]
