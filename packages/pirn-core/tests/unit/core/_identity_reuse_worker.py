"""Subprocess worker for the address-reuse regression loops (PIR-852).

Run as ``python _identity_reuse_worker.py <scenario> <iterations>``. It prints
one JSON object, ``{"iterations": n, "reuses": n, "collisions": n}``:

* ``reuses``: how many times the rebuilt object landed at the freed object's
  address, which is the precondition that makes the loop meaningful;
* ``collisions``: how many times it nonetheless matched the freed object (a
  shared token, an equal hash, or replay serving the recording).

The loops run in a fresh interpreter because, under a large coverage-traced
test-suite heap, CI saw no address reuse at all. The parent strips coverage's
subprocess hooks before starting this worker. Within the worker, reuse is made
deliberate rather than lucky; measured at 100% on Python 3.11 and 3.14:

1. Collect cyclic garbage first, while the victim is still held.
2. Empty the victim's attributes and drop it, so reference counting frees it
   and its block is the most recently freed one (:func:`release_by_refcount`).
3. Allocate replacements with a bare ``__new__`` into a list built *before*
   the free, and initialise only the one that claimed the address
   (:func:`claim_freed_address`). A fresh list, a range iterator or an
   ``__init__``'s helper objects are allocations too, and on 3.11 they share
   the victim's size class and take the block first.
"""

from __future__ import annotations

import asyncio
import gc
import json
import pickle
import sys
from collections.abc import Callable
from typing import Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.connectors.connector_base import ConnectorBase
from pirn.core.hashing import content_hash
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.security.credential_ref import CredentialRef
from pirn.tapestry import Tapestry


class Opaque(PirnOpaqueValue):
    """An identity-keyed opaque value that never calls ``super().__init__``."""

    def __init__(self, label: str) -> None:
        self.label = label


class OpaqueTuple(PirnOpaqueValue, tuple):
    """A value that cannot be weakly referenced (takes the ``__dict__`` fallback)."""


class PlainEndpointConnector(ConnectorBase):
    """A connector with configuration and no self-referencing attributes."""

    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url


class ReportsPlainEndpoint(Knot):
    """Holds a connector literal and returns its endpoint."""

    def __init__(self, *, connector: PlainEndpointConnector, **kwargs: Any) -> None:
        super().__init__(connector=connector, **kwargs)

    async def process(self, connector: PlainEndpointConnector, **_: Any) -> str:
        return connector.base_url


def release_by_refcount(value: Any) -> None:
    """Empty ``value``'s attributes so dropping the last reference frees it at once."""
    vars(value).clear()


def claim_freed_address(new_args: tuple[type], address: int, slots: list[Any]) -> Any:
    """Allocate bare ``new_args[0]`` instances into ``slots`` until one lands at ``address``.

    ``slots`` must be allocated before the victim is freed, and the loop avoids
    creating objects of its own (small-int counter, no iterator). ``new_args`` is
    the ``(cls,)`` tuple, also built before the free: ``cls.__new__(cls)`` would
    allocate a fresh argument tuple on every call, and that tuple can take the
    block.

    Returns:
        The uninitialised instance at ``address``, or the first one allocated
        if none landed there. The caller initialises it.
    """
    index = 0
    while index < len(slots):
        slots[index] = new_args[0].__new__(*new_args)
        if id(slots[index]) == address:
            return slots[index]
        index += 1
    return slots[0]


def opaque_hash_once() -> tuple[bool, bool]:
    """Free an :class:`Opaque`, build another at its address; compare token and hash."""
    slots: list[Any] = [None] * 1024
    new_args = (Opaque,)
    freed = Opaque("a")
    freed_address = id(freed)
    freed_token = freed._pirn_identity_token()
    freed_hash = content_hash(freed)
    gc.collect()
    release_by_refcount(freed)
    del freed
    fresh = claim_freed_address(new_args, freed_address, slots)
    fresh.__init__("b")
    collided = fresh._pirn_identity_token() == freed_token or content_hash(fresh) == freed_hash
    return id(fresh) == freed_address, collided


def connector_hash_once() -> tuple[bool, bool]:
    """Free a connector, build one with another credential at its address; compare hashes."""
    slots: list[Any] = [None] * 1024
    new_args = (ConnectorBase,)
    other_credential = CredentialRef(secret="sk-other")
    freed = ConnectorBase(credential=CredentialRef(secret="sk-recorded"))
    freed_address = id(freed)
    freed_hash = content_hash({"connector": freed})
    gc.collect()
    release_by_refcount(freed)
    del freed
    fresh = claim_freed_address(new_args, freed_address, slots)
    fresh.__init__(credential=other_credential)
    collided = content_hash({"connector": fresh}) == freed_hash
    return id(fresh) == freed_address, collided


def tuple_pickle_once() -> tuple[bool, bool]:
    """Pickle a non-weakrefable value, free it, unpickle at (usually) its address."""
    original = OpaqueTuple((1, 2))
    original_address = id(original)
    original_token = original._pirn_identity_token()
    payload = pickle.dumps(original)
    del original
    # Unpickling allocates temporaries that can take the freed block first and
    # release it again, so retry (freeing each miss) until the reuse happens.
    restored = pickle.loads(payload)
    for _ in range(8):
        if id(restored) == original_address:
            break
        del restored
        restored = pickle.loads(payload)
    return id(restored) == original_address, restored._pirn_identity_token() == original_token


async def connector_replay_once() -> tuple[bool, bool]:
    """Record with connector A, free it and its tapestry, replay with a new B.

    Only the history and data store survive. ``collided`` means replay served
    A's recording instead of refusing.
    """
    slots: list[Any] = [None] * 1024
    new_args = (PlainEndpointConnector,)
    history, data_store = InMemoryHistory(), InMemoryDataStore()
    recorded_connector = PlainEndpointConnector(base_url="https://a.example/v1")
    recorded_address = id(recorded_connector)
    with Tapestry(history=history, data_store=data_store) as recorded:
        ReportsPlainEndpoint(connector=recorded_connector, _config=KnotConfig(id="fetch"))
    run_id = (await recorded.run(RunRequest())).run_id
    del recorded
    gc.collect()
    release_by_refcount(recorded_connector)
    del recorded_connector

    fresh_connector = claim_freed_address(new_args, recorded_address, slots)
    fresh_connector.__init__(base_url="https://b.example/v1")
    reused = id(fresh_connector) == recorded_address
    with Tapestry(history=history, data_store=data_store) as replaying:
        ReportsPlainEndpoint(connector=fresh_connector, _config=KnotConfig(id="fetch"))
    session = await ReplaySession.from_history(history=history, run_id=run_id)
    try:
        await replaying.run(RunRequest(), replay=session)
    except ReplayMismatchError:
        return reused, False
    return reused, True


def tally_sync(step: Callable[[], tuple[bool, bool]], iterations: int) -> dict[str, int]:
    """Run a synchronous loop body ``iterations`` times."""
    reuses = collisions = 0
    for _ in range(iterations):
        reused, collided = step()
        reuses += reused
        collisions += collided
    return {"iterations": iterations, "reuses": reuses, "collisions": collisions}


async def tally_replay(iterations: int) -> dict[str, int]:
    """Run the replay loop body ``iterations`` times."""
    reuses = collisions = 0
    for _ in range(iterations):
        reused, collided = await connector_replay_once()
        reuses += reused
        collisions += collided
    return {"iterations": iterations, "reuses": reuses, "collisions": collisions}


def main(scenario: str, iterations: int) -> dict[str, int]:
    """Dispatch ``scenario`` and return its tally."""
    if scenario == "connector_replay":
        return asyncio.run(tally_replay(iterations))
    steps: dict[str, Callable[[], tuple[bool, bool]]] = {
        "opaque_hash": opaque_hash_once,
        "connector_hash": connector_hash_once,
        "tuple_pickle": tuple_pickle_once,
    }
    return tally_sync(steps[scenario], iterations)


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], int(sys.argv[2]))))
