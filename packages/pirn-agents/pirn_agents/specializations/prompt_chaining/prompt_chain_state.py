"""``PromptChainState`` — the value threaded through the prompt chain loop.

Internal API. See ``prompt_chain_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class PromptChainState(PirnOpaqueValue):
    """One link's worth of accumulated prompt-chain state.

    The loop reads its provider — and every other per-run input — from this value, not
    from instance attributes on the loop knot. Inputs held on the knot break two
    contracts: ``step``/``fold`` can then only be exercised through a constructor that
    re-supplies them, not called standalone with plain values (knot-design-rules.md
    Rules 2 and 4), and the state a run records in lineage omits what the run was
    actually driven by. It is also unsafe the moment such a loop is wired into a graph
    that outlives one invocation rather than rebuilt inside its pipeline's
    ``process()``, since the knot object is then shared by every run of that graph
    (PIR-873).

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        steps: The full, fixed instruction sequence decided at construction.
        llm: The provider every link's call runs on.
        index: How many links have run so far -- also the 0-based index of
            the next link to run.
        current: The input the next link runs against -- the original task
            before any link has run, or the previous link's output.
        outputs: Every link's output so far, in order.
    """

    steps: tuple[str, ...]
    llm: LLMProvider
    index: int
    current: str
    outputs: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "steps": list(self.steps),
            "llm": type(self.llm).__name__,
            "index": self.index,
            "current": self.current,
            "outputs": list(self.outputs),
        }
