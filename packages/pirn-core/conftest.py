"""pirn-core test fixtures + configuration (self-contained, no shared root)."""

from __future__ import annotations

import os

import pytest

# Tests run in a test environment. Set these env vars so that:
#   - _Signer.test_signer() is permitted (requires PIRN_ENV=test or ci)
#   - allow_unsigned=True on DataStores is permitted (requires PIRN_ALLOW_UNSIGNED=1)
os.environ.setdefault("PIRN_ENV", "test")
os.environ.setdefault("PIRN_ALLOW_UNSIGNED", "1")


@pytest.fixture(autouse=True)
def _pirn_test_env() -> None:
    """Re-assert the test-env guards before EVERY test.

    The security suite (tests/security/) pops PIRN_ENV / PIRN_ALLOW_UNSIGNED via
    ``os.environ.pop`` to exercise the production guards and does not restore
    them, which otherwise leaks into later tests (order-dependent). This runs
    before unittest ``setUp``, so those negative tests still pop the vars for
    their own assertions while everyone else gets a clean, guarded env.
    """
    os.environ["PIRN_ENV"] = "test"
    os.environ["PIRN_ALLOW_UNSIGNED"] = "1"


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


@pytest.fixture
def make_failed_run_result():
    """A RunResult with one exception record — used to test SubTapestryError."""
    from datetime import UTC, datetime

    from pirn.core.run_result import RunResult
    from pirn.managers.exception_record import ExceptionRecord

    exc = ExceptionRecord(
        run_id="r",
        knot_id="fail",
        exc_type="RuntimeError",
        message="inner failure",
        traceback_text="",
    )
    return RunResult(
        run_id="r",
        terminals_requested=["fail"],
        outputs={},
        exceptions=[exc],
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        dispatcher="local",
    )
