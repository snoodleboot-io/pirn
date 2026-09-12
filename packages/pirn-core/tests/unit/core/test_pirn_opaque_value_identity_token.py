"""The hardened per-instance identity token of :class:`PirnOpaqueValue` (PIR-852).

The old token was ``hex(id(self))``. CPython reuses a freed object's address, so
a new object could inherit a dead one's token, hash equal to it and be served
its recording on replay. These tests pin the replacement: a lazily assigned
random token that never repeats for a reused address, never survives a copy,
and holds no configuration.
"""

from __future__ import annotations

import copy
import gc
import pickle
import re
import threading

from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue


class Opaque(PirnOpaqueValue):
    """An opaque value that, like many subclasses, never calls ``super().__init__``."""

    def __init__(self, label: str) -> None:
        self.label = label


class OpaqueTuple(PirnOpaqueValue, tuple):
    """A subclass that cannot be weakly referenced (variable-size builtin base)."""


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


def test_non_weakrefable_subclass_gets_a_stable_token() -> None:
    # Arrange
    value = OpaqueTuple((1, 2))

    # Act
    tokens = {value._pirn_identity_token() for _ in range(3)}

    # Assert
    assert len(tokens) == 1


def test_non_weakrefable_subclass_copy_gets_its_own_token() -> None:
    # Arrange
    original = OpaqueTuple((1, 2))
    original_token = original._pirn_identity_token()

    # Act
    duplicate = copy.copy(original)
    duplicate_token = duplicate._pirn_identity_token()

    # Assert — copy.copy of a tuple subclass builds a new object at a new address.
    assert duplicate is not original
    assert duplicate_token != original_token


def _read_token_after_barrier(
    value: PirnOpaqueValue, barrier: threading.Barrier, seen: list[str]
) -> None:
    """Thread body: wait for every reader, then read the token once."""
    barrier.wait()
    seen.append(value._pirn_identity_token())
