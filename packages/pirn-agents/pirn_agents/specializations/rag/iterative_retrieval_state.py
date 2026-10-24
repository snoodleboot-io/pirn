"""``IterativeRetrievalState`` — state threaded across retrieve-and-refine rounds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore


@dataclass
class IterativeRetrievalState:
    """State threaded across retrieve-and-refine rounds."""

    original_query: str
    current_query: str
    memory: MemoryStore
    llm: LLMProvider
    max_iterations: int
    top_k: int
    merged: dict[str, Mapping[str, Any]] = field(default_factory=dict[str, Mapping[str, Any]])
    iteration: int = 0
    done: bool = False
