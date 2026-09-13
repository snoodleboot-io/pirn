"""``AsyncFanoutEngine`` is a deprecated, machinery-free shim (ADR agents-speaks-core WS1).

``ParallelToolExecutor`` fans out as one tool knot per call under an
``Aggregator`` and ``MapAgent`` runs on core's ``Map``/``Aggregator`` (WS4b),
so nothing composes the per-item retry/timeout/drain loop any more.  The
name stays importable for one cycle; constructing a subclass warns and the
old mechanics are gone.
"""

from __future__ import annotations

import warnings

from pirn_agents.agent._fanout_runner import _FanoutRunner
from pirn_agents.agent.async_fanout_engine import AsyncFanoutEngine
from pirn_agents.llm.retry_policy import RetryPolicy


class _Engine(AsyncFanoutEngine[str]):
    """A subclass the way the two engines used to be built."""


class TestDeprecatedShim:
    def test_constructing_a_subclass_warns(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _Engine()
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_the_machinery_is_gone(self) -> None:
        for name in ("run_with_retries", "drain_on_cancel", "_with_timeout"):
            assert not hasattr(AsyncFanoutEngine, name), name

    def test_the_fanout_runner_shim_still_warns(self) -> None:
        async def _sleep(_: float) -> None:
            return None

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            runner = _FanoutRunner(retry_policy=RetryPolicy(base_delay=0.0), rng=None, sleep=_sleep)
        assert isinstance(runner, AsyncFanoutEngine)
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
