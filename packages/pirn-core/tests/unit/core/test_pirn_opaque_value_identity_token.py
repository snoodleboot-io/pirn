"""The hardened per-instance identity token of :class:`PirnOpaqueValue` (PIR-852).

The old token was ``hex(id(self))``. CPython reuses a freed object's address, so
a new object could inherit a dead one's token, hash equal to it and be served
its recording on replay. These tests pin the replacement: a lazily assigned
random token that never repeats for a reused address, is not inherited by a
copy or an unpickled object (a shallow copy of a non-weakrefable instance is
the one documented exception), and holds no configuration.
"""

from __future__ import annotations

import copy
import gc
import pickle
import re
import threading
from collections.abc import Callable

import pytest

from pirn.connectors.connector_base import ConnectorBase
from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue


class Opaque(PirnOpaqueValue):
    """An opaque value that, like many subclasses, never calls ``super().__init__``."""

    def __init__(self, label: str) -> None:
        self.label = label


class OpaqueTuple(PirnOpaqueValue, tuple):
    """A subclass that cannot be weakly referenced (variable-size builtin base)."""


class TupleConnector(ConnectorBase, tuple):
    """A connector that cannot be weakly referenced; config lives in ``__dict__``."""


class OpaqueInt(PirnOpaqueValue, int):
    """An ``int``-derived subclass, also not weakly referenceable."""


class Slotted:
    """An object with neither ``__dict__`` nor weak-reference support."""

    __slots__ = ()


def test_token_is_stable_across_reads() -> None:
    # Arrange
    value = Opaque("a")

    # Act
    tokens = {value._pirn_identity_token() for _ in range(5)}

    # Assert
    assert len(tokens) == 1


def test_token_is_assigned_without_super_init() -> None:
    # Arrange
    value = Opaque("a")

    # Act
    token = value._pirn_identity_token()

    # Assert
    assert re.fullmatch(r"[0-9a-f]{32}", token)


def test_two_identically_configured_live_instances_get_different_tokens() -> None:
    # Arrange
    first, second = Opaque("same"), Opaque("same")

    # Act
    tokens = {first._pirn_identity_token(), second._pirn_identity_token()}

    # Assert
    assert len(tokens) == 2


def test_audit_form_is_type_name_at_token_and_does_not_embed_the_address() -> None:
    # Arrange
    value = Opaque("a")

    # Act
    audit = value._pirn_audit_dict()

    # Assert
    assert audit == f"<Opaque@{value._pirn_identity_token()}>"
    assert f"{id(value):x}" not in audit


def test_token_is_not_stored_in_instance_attributes() -> None:
    # Arrange
    value = Opaque("a")

    # Act
    value._pirn_identity_token()

    # Assert — copies, pickles and equality over vars() cannot see it.
    assert vars(value) == {"label": "a"}


def test_shallow_copy_gets_its_own_token() -> None:
    # Arrange
    original = Opaque("a")
    original_token = original._pirn_identity_token()

    # Act
    duplicate = copy.copy(original)

    # Assert
    assert duplicate._pirn_identity_token() != original_token
    assert original._pirn_identity_token() == original_token


def test_deep_copy_gets_its_own_token() -> None:
    # Arrange
    original = Opaque("a")
    original_token = original._pirn_identity_token()

    # Act
    duplicate = copy.deepcopy(original)

    # Assert
    assert duplicate._pirn_identity_token() != original_token


def test_unpickled_instance_gets_its_own_token() -> None:
    # Arrange
    original = Opaque("a")
    original_token = original._pirn_identity_token()

    # Act
    restored = pickle.loads(pickle.dumps(original))

    # Assert
    assert restored.label == "a"
    assert restored._pirn_identity_token() != original_token


def test_freed_instance_token_never_reappears_at_a_reused_address() -> None:
    # Arrange — free A, collect, allocate B, many times.
    iterations = 300
    reuses = 0
    collisions = 0

    # Act — freeze the existing heap so each full collection only walks
    # objects this loop created; otherwise gc.collect() dominates the suite.
    gc.freeze()
    try:
        for _ in range(iterations):
            freed = Opaque("a")
            freed_address = id(freed)
            freed_token = freed._pirn_identity_token()
            freed_hash = content_hash(freed)
            del freed
            gc.collect()
            fresh = Opaque("b")
            reuses += id(fresh) == freed_address
            collisions += fresh._pirn_identity_token() == freed_token
            collisions += content_hash(fresh) == freed_hash
            del fresh
    finally:
        gc.unfreeze()

    # Assert — the loop only proves something if addresses were really reused.
    assert reuses > 0, "no address was reused; the regression loop tested nothing"
    assert collisions == 0


def test_registry_does_not_retain_freed_instances() -> None:
    # Arrange
    registry = PirnOpaqueValue._pirn_identity_registry
    before = len(registry)

    # Act
    for index in range(200):
        value = Opaque(str(index))
        value._pirn_identity_token()
        del value
    gc.collect()

    # Assert
    assert len(registry) <= before


def test_concurrent_first_reads_agree_on_one_token() -> None:
    # Arrange
    value = Opaque("a")
    seen: list[str] = []
    barrier = threading.Barrier(8)
    threads = [
        threading.Thread(target=_read_token_after_barrier, args=(value, barrier, seen))
        for _ in range(8)
    ]

    # Act
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Assert
    assert len(set(seen)) == 1
    assert seen[0] == value._pirn_identity_token()


@pytest.mark.parametrize("build", [lambda: OpaqueTuple((1, 2)), lambda: OpaqueInt(7)])
def test_non_weakrefable_subclass_gets_a_stable_token(build: Callable[[], PirnOpaqueValue]) -> None:
    # Arrange
    value = build()

    # Act
    tokens = {value._pirn_identity_token() for _ in range(3)}

    # Assert
    assert len(tokens) == 1
    assert re.fullmatch(r"[0-9a-f]{32}", tokens.pop())


def test_two_equal_non_weakrefable_instances_get_different_tokens() -> None:
    # Arrange
    first, second = OpaqueTuple((1, 2)), OpaqueTuple((1, 2))

    # Act
    tokens = {first._pirn_identity_token(), second._pirn_identity_token()}

    # Assert
    assert len(tokens) == 2


@pytest.mark.parametrize("build", [lambda: OpaqueTuple((1, 2)), lambda: OpaqueInt(7)])
def test_non_weakrefable_unpickled_instance_gets_its_own_token(
    build: Callable[[], PirnOpaqueValue],
) -> None:
    # Arrange
    original = build()
    original_token = original._pirn_identity_token()

    # Act
    restored = pickle.loads(pickle.dumps(original))

    # Assert
    assert restored == original
    assert restored._pirn_identity_token() != original_token


def test_non_weakrefable_deep_copy_gets_its_own_token() -> None:
    # Arrange
    original = OpaqueTuple((1, 2))
    original_token = original._pirn_identity_token()

    # Act
    duplicate = copy.deepcopy(original)

    # Assert
    assert duplicate._pirn_identity_token() != original_token


def test_non_weakrefable_token_never_survives_pickle_free_unpickle_at_the_same_address() -> None:
    # Arrange — the probe that defeated the id()-owner check: pickle A, free
    # it, unpickle into (usually) the same address.
    iterations = 2000
    reuses = 0
    collisions = 0

    # Act
    for _ in range(iterations):
        reused, collided = _pickle_free_unpickle_once()
        reuses += reused
        collisions += collided

    # Assert
    assert reuses > 0, "no address was reused; the regression loop tested nothing"
    assert collisions == 0


def test_non_weakrefable_mutated_shallow_copy_does_not_hash_equal_to_the_original() -> None:
    # Arrange — copy.copy shares the instance dict's values, nonce included.
    # A connector is the realistic case: content_hash reaches the token through
    # ConnectorBase.__pirn_canonical__ (a bare tuple subclass hashes its items).
    original = TupleConnector()
    original.base_url = "https://a.example/v1"
    original_hash = content_hash({"value": original})
    duplicate = copy.copy(original)

    # Act
    duplicate.base_url = "https://b.example/v1"
    duplicate_hash = content_hash({"value": duplicate})

    # Assert
    assert duplicate_hash != original_hash
    assert content_hash({"value": original}) == original_hash


def test_mutated_shallow_copy_does_not_hash_equal_to_the_original() -> None:
    # Arrange — the weakref-registry path: the copy is a new object with no entry.
    original = Opaque("https://a.example/v1")
    original_hash = content_hash({"value": original})
    duplicate = copy.copy(original)

    # Act
    duplicate.label = "https://b.example/v1"
    duplicate_hash = content_hash({"value": duplicate})

    # Assert
    assert duplicate_hash != original_hash
    assert content_hash({"value": original}) == original_hash


def test_instance_without_a_dict_refuses_with_a_fresh_token_per_read() -> None:
    # Arrange — unreachable for a real subclass (this mixin has no __slots__),
    # so the fallback is exercised directly on a slotted object.
    value = Slotted()

    # Act
    tokens = {PirnOpaqueValue._pirn_instance_identity_token(value) for _ in range(5)}  # type: ignore[arg-type]

    # Assert — it never matches anything, itself included.
    assert len(tokens) == 5


def _pickle_free_unpickle_once() -> tuple[bool, bool]:
    """Pickle a tuple-derived value, free it, unpickle it.

    Returns:
        ``(reused, collided)``: whether the unpickled value landed at the
        original's address, and whether it came back with the original's token.
    """
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


def _read_token_after_barrier(
    value: PirnOpaqueValue, barrier: threading.Barrier, seen: list[str]
) -> None:
    """Thread body: wait for every reader, then read the token once."""
    barrier.wait()
    seen.append(value._pirn_identity_token())
