"""``RetryPolicy`` — jittered exponential backoff configuration.

A frozen, provider-neutral value describing how a
:class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider` retries a failed
request: how many attempts, and how long to wait between them. The delay grows
exponentially and is capped, then optionally has *full jitter* applied
(``uniform(0, delay)``) to avoid synchronised retry storms across a batch of
concurrent calls.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RetryPolicy(PirnOpaqueValue):
    """How many times, and how long, to back off between retries.

    Attributes
    ----------
    max_retries:
        Maximum number of *retries* after the first attempt (so total
        attempts is ``max_retries + 1``). ``0`` disables retrying.
    base_delay:
        The un-jittered delay before the first retry, in seconds.
    max_delay:
        Ceiling on the exponential delay, in seconds.
    multiplier:
        Growth factor applied per attempt (``2.0`` doubles each time).
    jitter:
        When ``True``, full jitter is applied: the returned delay is a
        uniform draw in ``[0, capped_delay)``.
    """

    max_retries: int = 2
    base_delay: float = 0.05
    max_delay: float = 2.0
    multiplier: float = 2.0
    jitter: bool = True

    def backoff_delay(self, attempt: int, *, rng: Callable[[], float] | None = None) -> float:
        """Return the delay before retry ``attempt`` (0-based), in seconds.

        Args:
            attempt: The 0-based retry index (0 is the first retry).
            rng: Optional zero-arg callable returning a float in ``[0, 1)``
                used for the jitter draw; defaults to :func:`random.random`.
                Injected in tests for deterministic delays.

        Returns:
            The capped exponential delay, with full jitter applied when
            :attr:`jitter` is set.
        """
        raw = self.base_delay * (self.multiplier**attempt)
        capped = min(self.max_delay, raw)
        if not self.jitter:
            return capped
        draw = rng() if rng is not None else random.random()
        return capped * draw

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "multiplier": self.multiplier,
            "jitter": self.jitter,
        }
