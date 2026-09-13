"""``AsyncFanoutEngine`` — deprecated (one cycle); the engine owns fan-out now.

This mixin once held the per-item mechanics both
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor` and
:class:`~pirn_agents.batch.map_agent.MapAgent` duplicated: the timeout
wrapper, the jittered exponential backoff, the retry-with-terminal-timeout
structure and the cancel-and-drain.  Since the ADR "agents speaks core" the
executor wires one tool knot per call under an ``Aggregator`` (WS1) and
``MapAgent`` runs on core's ``Map``/``Aggregator`` (WS4b), with per-knot
timeout and retry run by ``GovernedDispatch`` (``KnotConfig.timeout`` /
``KnotConfig.retry``) and cancellation drained by the engine.  Nothing composes
this class any more; the name stays importable for the cycle, constructing a
subclass warns, and the mechanics are gone.
"""

from __future__ import annotations

import warnings
from typing import Any, Generic, TypeVar

R = TypeVar("R")


class AsyncFanoutEngine(Generic[R]):
    """Deprecated, machinery-free base kept importable for one cycle."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warnings.warn(
            "AsyncFanoutEngine is deprecated (ADR agents-speaks-core WS1/WS4b): fan-out is "
            "one knot per item under an Aggregator; per-item timeout and retry are "
            "KnotConfig.timeout / KnotConfig.retry, run by the engine",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
