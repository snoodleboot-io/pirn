"""Mock-driver tests for the ValKey backend.

Uses a fake valkey-glide client that records every operation and
returns canned responses.  Real-server tests are gated by
``@pytest.mark.needs_valkey`` (see ``docs/real-backend-testing-plan.md``).
"""

from __future__ import annotations

import pickle

import pytest

from pirn import KnotConfig, Parameter, knot
from pirn.backends.valkey import ValKeyDataStore, ValKeyStore

# ---------------------------------------------------- fake glide client


class _FakeGlideClient:
    """Fake valkey-glide client with the methods our backends use."""

    def __init__(self) -> None:
        # Hash storage: {key: {field: value}}
        self.hashes: dict[str, dict[str, str]] = {}
        # Set storage: {key: set[str]}
        self.sets: dict[str, set[str]] = {}
        # String storage: {key: bytes}
        self.strings: dict[str, bytes] = {}
        # TTL recording (for tests that care about expiry).
        self.ttls: dict[str, int] = {}

    async def hset(self, key: str, fields: dict[str, str]) -> int:
        existing = self.hashes.setdefault(key, {})
        existing.update(fields)
        return len(fields)

    async def sadd(self, key: str, members: list[str]) -> int:
        s = self.sets.setdefault(key, set())
        before = len(s)
        s.update(members)
        return len(s) - before

    async def set(self, key: str, value: bytes, expiry: object = None) -> str:
        self.strings[key] = value
        if expiry is not None:
            # Accept both raw ints (legacy) and ExpirySet objects.
            from glide import ExpirySet

            if isinstance(expiry, ExpirySet):
                self.ttls[key] = int(expiry.value)
            else:
                self.ttls[key] = expiry
        return "OK"

    async def get(self, key: str) -> bytes | None:
        return self.strings.get(key)

    async def exists(self, keys: list[str]) -> int:
        return sum(1 for k in keys if k in self.strings)

    async def delete(self, keys: list[str]) -> int:
        n = 0
        for k in keys:
            if k in self.strings:
                del self.strings[k]
                n += 1
        return n

    async def close(self) -> None:
        pass


# ---------------------------------------------------- ValKeyStore tests


@knot
async def _f(x: int) -> int:
    return x


async def test_valkey_store_aregister_writes_hash_and_set_membership():
    client = _FakeGlideClient()
    store = ValKeyStore(client=client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)

    # Should have written the knot hash.
    knot_key = "pirn:tapestry:knot:px"
    assert knot_key in client.hashes
    assert "knot_class" in client.hashes[knot_key]
    assert "config_json" in client.hashes[knot_key]
    assert "parents_json" in client.hashes[knot_key]

    # Should have added the id to the membership set.
    assert "pirn:tapestry:ids" in client.sets
    assert "px" in client.sets["pirn:tapestry:ids"]


async def test_valkey_store_local_cache_serves_get():
    client = _FakeGlideClient()
    store = ValKeyStore(client=client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)
    assert store.get("px") is p
    assert store.get("missing") is None


async def test_valkey_store_rejects_duplicate_id_different_instance():
    client = _FakeGlideClient()
    store = ValKeyStore(client=client)
    p1 = Parameter("x", int, _config=KnotConfig(id="dup"))
    await store.aregister(p1)
    p2 = Parameter("y", int, _config=KnotConfig(id="dup"))
    with pytest.raises(ValueError, match="already registered"):
        await store.aregister(p2)


async def test_valkey_store_idempotent_same_instance():
    client = _FakeGlideClient()
    store = ValKeyStore(client=client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)
    await store.aregister(p)  # no error
    assert len(store.all()) == 1


async def test_valkey_store_snapshot_lists_local_ids():
    client = _FakeGlideClient()
    store = ValKeyStore(client=client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    q = Parameter("y", int, _config=KnotConfig(id="py"))
    await store.aregister(p)
    await store.aregister(q)
    snap = store.snapshot()
    assert sorted(snap.knot_ids) == ["px", "py"]


async def test_valkey_store_records_full_class_path():
    """The stored class must be the full module-qualified name so
    cross-process code can look it up."""
    client = _FakeGlideClient()
    store = ValKeyStore(client=client)
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    await store.aregister(p)
    knot_class = client.hashes["pirn:tapestry:knot:px"]["knot_class"]
    assert "Parameter" in knot_class
    assert "." in knot_class  # module-qualified


# ---------------------------------------------------- ValKeyDataStore tests


async def test_valkey_data_store_put_pickles_value():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)
    await ds.put("sha256:abc", {"key": "value"})

    stored = client.strings["pirn:data:sha256:abc"]
    assert pickle.loads(stored) == {"key": "value"}


async def test_valkey_data_store_get_unpickles():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)
    await ds.put("sha256:abc", [1, 2, 3])
    assert await ds.get("sha256:abc") == [1, 2, 3]


async def test_valkey_data_store_get_missing_raises_keyerror():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)
    with pytest.raises(KeyError):
        await ds.get("sha256:nope")


async def test_valkey_data_store_has():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)
    assert not await ds.has("sha256:k")
    await ds.put("sha256:k", 1)
    assert await ds.has("sha256:k")


async def test_valkey_data_store_scrub_removes():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)
    await ds.put("sha256:k", "v")
    await ds.scrub("sha256:k")
    assert not await ds.has("sha256:k")


async def test_valkey_data_store_ttl_propagates():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client, ttl_seconds=300)
    await ds.put("sha256:expiring", "v")
    assert client.ttls["pirn:data:sha256:expiring"] == 300


async def test_valkey_data_store_no_ttl_when_unspecified():
    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)
    await ds.put("sha256:permanent", "v")
    assert "pirn:data:sha256:permanent" not in client.ttls


async def test_valkey_data_store_round_trips_complex_objects():
    """Pickle handles arbitrary Python objects; test a few shapes."""
    from pirn import KnotLineage

    client = _FakeGlideClient()
    ds = ValKeyDataStore(client=client)

    rec = KnotLineage(
        run_id="r",
        knot_id="k",
        knot_class="m.K",
        knot_config_hash="sha256:cfg",
        outcome="ok",
        dispatcher="LocalDispatcher",
        output_hash="sha256:out",
    )
    await ds.put("sha256:rec", rec)
    fetched = await ds.get("sha256:rec")
    assert fetched.run_id == rec.run_id
    assert fetched.knot_id == rec.knot_id
