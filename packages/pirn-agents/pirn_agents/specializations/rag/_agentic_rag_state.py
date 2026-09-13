"""``_AgenticRagState`` — state threaded across agentic-RAG rounds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _AgenticRagState:
    """State threaded across agentic-RAG rounds."""

    current_question: str
    answer: str = ""
    iteration: int = 0
    done: bool = False
