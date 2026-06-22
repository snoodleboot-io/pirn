"""Session-scoped Ray cluster fixture shared across all Ray tests."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def ray_cluster():
    try:
        import ray
    except ImportError:
        yield
        return

    if not ray.is_initialized():
        ray.init(num_cpus=2, ignore_reinit_error=True, log_to_driver=False)
    yield
    ray.shutdown()
