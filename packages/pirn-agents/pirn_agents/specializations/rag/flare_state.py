"""``FlareState`` — the value threaded through the FLARE sentence-generation loop.

Internal API. See ``flare_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore


@dataclass(frozen=True)
class FlareState:
    """One round's worth of accumulated FLARE generation state.

    Frozen; ``afold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        parts: The assembled answer sentences so far, in order.
        retrieval_calls: How many retrieval calls have been spent so far.
        done: Whether the model signalled ``DONE``.
        index: How many rounds have completed (bounds the loop even when a
            round produces an empty sentence, matching the original
            ``for _step in range(max_sentences)``).
    """

    parts: tuple[str, ...]
    retrieval_calls: int
    done: bool
    index: int
    query: str
    memory: MemoryStore
    llm: LLMProvider
    confidence_threshold: float
    max_sentences: int
    max_retrieval_calls: int
    top_k: int
