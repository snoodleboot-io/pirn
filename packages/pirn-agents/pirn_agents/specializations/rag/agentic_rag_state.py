"""``AgenticRagState`` — state threaded across agentic-RAG rounds."""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.tools.tool_factory import ToolFactory


@dataclass
class AgenticRagState:
    """State threaded across agentic-RAG rounds."""

    current_question: str
    query: str
    rag_tool: ToolFactory
    llm: LLMProvider
    max_iterations: int
    answer: str = ""
    iteration: int = 0
    done: bool = False
