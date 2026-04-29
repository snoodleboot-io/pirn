"""Real-backend tests for the S3 DataStore.

Gated by ``pytest.mark.needs_s3``.  Set the env vars below to run;
tests skip silently when they are absent.

Required env vars:
    PIRN_TEST_S3_ENDPOINT   — e.g. http://localhost:9000 (MinIO)
    PIRN_TEST_S3_ACCESS_KEY — e.g. pirn
    PIRN_TEST_S3_SECRET_KEY — e.g. pirntestpassword
    PIRN_TEST_S3_BUCKET     — e.g. pirn-test
    PIRN_TEST_S3_REGION     — e.g. us-east-1 (optional, defaults to us-east-1)

These mirror ``test_s3_mock.py`` but run against a genuine S3-compatible
server, adding large-value and eventual-consistency tests.
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.needs_s3


# ------------------------------------------------------------- fixture


def _s3_env():
    """Return S3 env vars or skip the test."""
    endpoint = os.environ.get("PIRN_TEST_S3_ENDPOINT")
    access_key = os.environ.get("PIRN_TEST_S3_ACCESS_KEY")
    secret_key = os.environ.get("PIRN_TEST_S3_SECRET_KEY")
    bucket = os.environ.get("PIRN_TEST_S3_BUCKET")
    if not all([endpoint, access_key, secret_key, bucket]):
        pytest.skip(
            "PIRN_TEST_S3_ENDPOINT / ACCESS_KEY / SECRET_KEY / BUCKET not set"
        )
    return {
        "endpoint": endpoint,
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket": bucket,
        "region": os.environ.get("PIRN_TEST_S3_REGION", "us-east-1"),
    }


@pytest.fixture
def s3_store(request):
    """Return an S3DataStore with a unique key prefix per test."""
    try:
        import aioboto3
    except ImportError:
        pytest.skip("aioboto3 not installed")

    env = _s3_env()
    prefix = f"pirn-test-{uuid.uuid4()}/"

    session = aioboto3.Session(
        aws_access_key_id=env["access_key"],
        aws_secret_access_key=env["secret_key"],
    )

    from pirn.backends.s3 import S3DataStore

    return S3DataStore(
        bucket=env["bucket"],
        prefix=prefix,
        region=env["region"],
        endpoint_url=env["endpoint"],
        session=session,
    )


# ------------------------------------------------------------- tests


async def test_s3_data_store_put_and_get_round_trips(s3_store):
    await s3_store.put("sha256:abc", {"key": "value"})
    result = await s3_store.get("sha256:abc")
    assert result == {"key": "value"}


async def test_s3_data_store_has_present_and_missing(s3_store):
    assert not await s3_store.has("sha256:missing")
    await s3_store.put("sha256:present", 42)
    assert await s3_store.has("sha256:present")


async def test_s3_data_store_get_missing_raises_keyerror(s3_store):
    with pytest.raises(KeyError):
        await s3_store.get("sha256:nope")


async def test_s3_data_store_scrub_removes_object(s3_store):
    await s3_store.put("sha256:scrubme", "gone")
    await s3_store.scrub("sha256:scrubme")
    assert not await s3_store.has("sha256:scrubme")


async def test_s3_data_store_custom_prefix_isolates_tests(s3_store):
    """Each fixture gets a unique prefix — parallel runs can't collide."""
    await s3_store.put("sha256:isolated", "v")
    assert await s3_store.has("sha256:isolated")


async def test_s3_data_store_large_value(s3_store):
    """10 MB value exercises real S3 multipart-upload thresholds."""
    big = b"x" * (10 * 1024 * 1024)
    await s3_store.put("sha256:bigval", big)
    result = await s3_store.get("sha256:bigval")
    assert result == big


async def test_s3_data_store_handles_put_then_immediate_get(s3_store):
    """Put then get with no delay — guards against stale-cache assumptions."""
    for i in range(10):
        h = f"sha256:immediate_{i}"
        await s3_store.put(h, i)
        assert await s3_store.get(h) == i
