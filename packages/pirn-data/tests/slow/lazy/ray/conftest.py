"""Shared fixtures for Ray Data Tier-3 unit tests.

We avoid calling ``ray.init()`` at module level — Ray's cluster startup
is heavy. Instead, a session-scoped autouse fixture starts a single
local Ray runtime once per test session and tears it down at the end.

Tests use ``ray.data.from_items(...)`` to avoid the cost of distributed
data movement; these tests exercise the wiring of the Tier-3 knots,
not Ray Data's distributed execution.
"""

from __future__ import annotations

import pytest

ray = pytest.importorskip("ray")
pytest.importorskip("ray.data")


@pytest.fixture(scope="session", autouse=True)
def _ray_session():
    """Start a single Ray runtime once per test session."""
    started_here = False
    if not ray.is_initialized():
        ray.init(
            include_dashboard=False,
            ignore_reinit_error=True,
            log_to_driver=False,
            num_cpus=1,
        )
        started_here = True
    yield
    if started_here:
        ray.shutdown()
