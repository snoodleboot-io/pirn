"""Real-backend tests for the ValKey backend.

Gated by ``pytest.mark.needs_valkey``.  Set ``PIRN_TEST_VALKEY_URL``
to run; tests skip silently when it is absent.

These mirror ``test_valkey_mock.py`` but run against a genuine ValKey
server, adding TTL expiry and concurrency tests that mocks cannot cover.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter

pytestmark = pytest.mark.needs_valkey


# ------------------------------------------------------------- fixture


def _parse_valkey_url(url: str):
    """Extract host and port from ``redis://host:port/db``."""
    url = url.removeprefix("redis://").removeprefix("valkey://")
    host_port = url.split("/")[0]
    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        return host, int(port_str)
    return host_port, 6379


@pytest.fixture
async def valkey_client():
    url = os.environ.get("PIRN_TEST_VALKEY_URL")
    if not url:
        pytest.skip("PIRN_TEST_VALKEY_URL not set")

    try:
        from glide import GlideClient, GlideClientConfiguration, NodeAddress
    except ImportError:
        pytest.skip("valkey-glide not installed")

    host, port = _parse_valkey_url(url)
    config = GlideClientConfiguration([NodeAddress(host=host, port=port)])
    client = await GlideClient.create(config)

    # Flush only this DB (test-only instance).
    await client.flushdb()

    yield client
    await client.close()


# ------------------------------------------------------------- helpers


@knot
async def _double(x: int) -> int:
    return x * 2


# ------------------------------------------------------------- store tests


async def test_valkey_store_aregister_writes_hash_and_membership(valkey_client):
    from pirn.backends.valkey.valkey_store import ValKeyStore

    store = ValKeyStore(client=valkey_client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)

    knot_key = b"pirn:tapestry:knot:px"
    stored = await valkey_client.hgetall(knot_key)
    assert stored is not None
    assert b"knot_class" in stored or "knot_class" in stored

    members = await valkey_client.smembers("pirn:tapestry:ids")
    assert b"px" in members or "px" in members


async def test_valkey_store_local_cache_serves_get(valkey_client):
    from pirn.backends.valkey.valkey_store import ValKeyStore

    store = ValKeyStore(client=valkey_client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)
    assert store.get("px") is p
    assert store.get("missing") is None


async def test_valkey_store_rejects_duplicate_id_different_instance(valkey_client):
    from pirn.backends.valkey.valkey_store import ValKeyStore

    store = ValKeyStore(client=valkey_client)
    p1 = Parameter("x", int, _config=KnotConfig(id="dup"))
    await store.aregister(p1)
    p2 = Parameter("y", int, _config=KnotConfig(id="dup"))
    with pytest.raises(ValueError, match="already registered"):
        await store.aregister(p2)


async def test_valkey_store_idempotent_same_instance(valkey_client):
    from pirn.backends.valkey.valkey_store import ValKeyStore

    store = ValKeyStore(client=valkey_client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)
    await store.aregister(p)
    assert len(store.all()) == 1


# ------------------------------------------------------------- data store tests


async def test_valkey_data_store_put_and_get_round_trips(valkey_client):
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    ds = ValKeyDataStore(client=valkey_client, allow_unsigned=True)
    await ds.put("sha256:abc", {"key": "value"})
    result = await ds.get("sha256:abc")
    assert result == {"key": "value"}


async def test_valkey_data_store_has_present_and_missing(valkey_client):
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    ds = ValKeyDataStore(client=valkey_client, allow_unsigned=True)
    assert not await ds.has("sha256:missing")
    await ds.put("sha256:present", 42)
    assert await ds.has("sha256:present")


async def test_valkey_data_store_scrub_removes_key(valkey_client):
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    ds = ValKeyDataStore(client=valkey_client, allow_unsigned=True)
    await ds.put("sha256:scrubme", "value")
    await ds.scrub("sha256:scrubme")
    assert not await ds.has("sha256:scrubme")


async def test_valkey_data_store_get_missing_raises_keyerror(valkey_client):
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    ds = ValKeyDataStore(client=valkey_client, allow_unsigned=True)
    with pytest.raises(KeyError):
        await ds.get("sha256:nope")


async def test_valkey_data_store_ttl_actually_expires(valkey_client):
    """TTL expiry requires a real server — a mock can't verify this."""
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    ds = ValKeyDataStore(client=valkey_client, ttl_seconds=1, allow_unsigned=True)
    await ds.put("sha256:expiring", "gone soon")
    assert await ds.has("sha256:expiring")

    await asyncio.sleep(2)
    assert not await ds.has("sha256:expiring")


async def test_valkey_data_store_concurrent_put_get(valkey_client):
    """100 parallel puts followed by 100 gets must all round-trip."""
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    ds = ValKeyDataStore(client=valkey_client, allow_unsigned=True)
    hashes = [f"sha256:concurrent_{i}" for i in range(100)]

    await asyncio.gather(*[ds.put(h, i) for i, h in enumerate(hashes)])
    results = await asyncio.gather(*[ds.get(h) for h in hashes])

    for i, value in enumerate(results):
        assert value == i
