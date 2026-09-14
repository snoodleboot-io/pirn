"""``PromptChainState`` — the value threaded through the prompt chain loop.

Internal API. See ``prompt_chain_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptChainState:
    """One link's worth of accumulated prompt-chain state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        steps: The full, fixed instruction sequence decided at construction.
        index: How many links have run so far -- also the 0-based index of
            the next link to run.
        current: The input the next link runs against -- the original task
            before any link has run, or the previous link's output.
        outputs: Every link's output so far, in order.
    """

    steps: tuple[str, ...]
    index: int
    current: str
    outputs: tuple[str, ...]
