"""``SessionContext`` — the immutable session state that travels on real data edges.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, replace
from typing import Any

from examples.llm_agent.agent_loop.step_result import StepResult


@dataclass(frozen=True)
class SessionContext:
    messages: tuple[str, ...]
    run_seed: int
    msg_idx: int = 0
    msg_iteration: int = 0
    iteration: int = 0
    scratchpad: tuple[StepResult, ...] = ()
    responses: tuple[str, ...] = ()

    @property
    def current_message(self) -> str:
        return self.messages[self.msg_idx]

    @property
    def done(self) -> bool:
        return self.msg_idx >= len(self.messages)

    def evolve(self, **changes: Any) -> SessionContext:
        return replace(self, **changes)

    def rng(self, extra: str = "") -> random.Random:
        """Deterministic RNG seeded from current message + run_seed + iteration."""
        key = f"{self.current_message}|{self.run_seed}|{self.iteration}|{extra}"
        seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)
