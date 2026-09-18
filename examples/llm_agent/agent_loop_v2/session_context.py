"""``SessionContext`` — the immutable session state that travels on real data edges.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, replace
from typing import Any

from pirn_agents.types.messaging.agent_message import AgentMessage

from examples.llm_agent.agent_loop_v2.step_result import StepResult


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

    def seed_messages(self, system: str) -> tuple[AgentMessage, ...]:
        """The system + user turn an inner agent pipeline starts from."""
        prior = " | ".join(s.response.data[:60] for s in self.scratchpad[-3:])
        user_content = self.current_message
        if prior:
            user_content = f"{user_content}\n\nPrior findings: {prior}"
        return (
            AgentMessage(role="system", content=system),
            AgentMessage(role="user", content=user_content),
        )
