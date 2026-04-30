"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--real",
        action="store_true",
        default=False,
        help="Run real-backend tests (requires services from scripts/test-env-up.sh)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip needs_* tests unless --real is passed."""
    if config.getoption("--real"):
        return

    # Map marker → human-readable reason.
    real_markers = {
        "needs_postgres": "pass --real to run Postgres tests",
        "needs_valkey": "pass --real to run ValKey tests",
        "needs_kafka": "pass --real to run Kafka tests",
        "needs_s3": "pass --real to run S3 tests",
        "needs_dask": "pass --real to run Dask tests",
        "needs_ray": "pass --real to run Ray tests",
        "needs_celery": "pass --real to run Celery tests",
    }
    for item in items:
        for marker, reason in real_markers.items():
            if item.get_closest_marker(marker):
                item.add_marker(pytest.mark.skip(reason=reason))
                break


@pytest.fixture
def tapestry():
    from pirn.tapestry import Tapestry

    return Tapestry()
