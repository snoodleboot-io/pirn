"""The hardened per-instance identity token of :class:`PirnOpaqueValue` (PIR-852).

The old token was ``hex(id(self))``. CPython reuses a freed object's address, so
a new object could inherit a dead one's token, hash equal to it and be served
its recording on replay. These tests pin the replacement: a lazily assigned
random token that never repeats for a reused address, is not inherited by a
copy or an unpickled object, and holds no configuration.

The address-reuse loops run in a subprocess (:class:`IdentityReuseSubprocess`):
inside a large, coverage-traced test process the allocator stopped reusing
addresses at all, so an in-process loop could not exercise the hazard.
"""

from __future__ import annotations

import copy
import gc
import pickle
import re
import threading
from collections.abc import Callable

import pytest

import pirn.core.pirn_identity_nonce as pirn_identity_nonce_module
import pirn.core.pirn_opaque_value as pirn_opaque_value_module
from pirn.connectors.connector_base import ConnectorBase
from pirn.core.content_hasher import ContentHasher
from pirn.core.pirn_identity_nonce import PirnIdentityNonce
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from tests.unit.core.identity_reuse_subprocess import IdentityReuseSubprocess


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
    # Arrange — free A, collect, allocate B, many times, in a clean interpreter.

    # Act
    tally = IdentityReuseSubprocess.run("opaque_hash", 200)

    # Assert — the loop only proves something if addresses were really reused.
    assert tally["reuses"] > 0, f"no address was reused; the loop tested nothing: {tally}"
    assert tally["collisions"] == 0, tally


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


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_non_weakrefable_pickle_payload_never_carries_the_identity_token(protocol: int) -> None:
    # Arrange — if the token is not in the bytes, no unpickled object can
    # recover it, whatever address it lands at.
    original = OpaqueTuple((1, 2))
    token = original._pirn_identity_token()

    # Act
    payload = pickle.dumps(original, protocol=protocol)

    # Assert
    assert token.encode("ascii") not in payload
    assert token.encode("utf-16-le") not in payload


def test_non_weakrefable_unpickled_value_at_the_originals_address_mints_its_own_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — the probe that defeated the old id()-owner check: an object
    # unpickled into the freed original's address. Real reuse depends on the
    # allocator and was flaky in CI (PIR-855), so the address match is
    # simulated: every object reports the same id() to the owner checks.
    _report_one_address_for_every_object(monkeypatch)
    original = OpaqueTuple((1, 2))
    original_token = original._pirn_identity_token()
    payload = pickle.dumps(original)
    del original

    # Act
    restored = pickle.loads(payload)

    # Assert
    assert restored._pirn_identity_token() != original_token


def test_non_weakrefable_deep_copy_at_the_originals_address_mints_its_own_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — as above, for a deepcopy that lands at the original's address.
    _report_one_address_for_every_object(monkeypatch)
    original = OpaqueTuple((1, 2))
    original_token = original._pirn_identity_token()

    # Act
    duplicate = copy.deepcopy(original)

    # Assert
    assert duplicate._pirn_identity_token() != original_token


def test_non_weakrefable_holder_minted_for_another_owner_is_not_trusted() -> None:
    # Arrange — a holder in this instance's __dict__ whose owner is another
    # object (or nobody) must not lend its token.
    value = OpaqueTuple((1, 2))
    borrowed = PirnIdentityNonce(owner_id=id(value) + 16)
    ownerless = PirnIdentityNonce()
    tokens = []

    # Act
    for holder in (borrowed, ownerless):
        vars(value)["_pirn_identity_nonce"] = holder
        tokens.append(value._pirn_identity_token())

    # Assert
    assert tokens[0] != borrowed.token
    assert tokens[1] != ownerless.token


def test_simulated_shared_address_would_expose_an_id_only_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — control for the simulation: with every object at one address,
    # a token keyed on id() alone collides. The tests above therefore exercise
    # the hazard rather than passing vacuously.
    _report_one_address_for_every_object(monkeypatch)
    first, second = OpaqueTuple((1,)), OpaqueTuple((2,))

    # Act
    ids = {pirn_identity_nonce_module.id(first), pirn_identity_nonce_module.id(second)}  # type: ignore[attr-defined]

    # Assert
    assert len(ids) == 1
    assert first._pirn_identity_token() != second._pirn_identity_token()


def test_non_weakrefable_mutated_shallow_copy_does_not_hash_equal_to_the_original() -> None:
    # Arrange — copy.copy shares the instance dict's values, nonce included.
    # A connector is the realistic case: content_hash reaches the token through
    # ConnectorBase.__pirn_canonical__ (a bare tuple subclass hashes its items).
    original = TupleConnector()
    original.base_url = "https://a.example/v1"
    original_hash = ContentHasher.hash({"value": original})
    duplicate = copy.copy(original)

    # Act
    duplicate.base_url = "https://b.example/v1"
    duplicate_hash = ContentHasher.hash({"value": duplicate})

    # Assert
    assert duplicate_hash != original_hash
    assert ContentHasher.hash({"value": original}) == original_hash


def test_mutated_shallow_copy_does_not_hash_equal_to_the_original() -> None:
    # Arrange — the weakref-registry path: the copy is a new object with no entry.
    original = Opaque("https://a.example/v1")
    original_hash = ContentHasher.hash({"value": original})
    duplicate = copy.copy(original)

    # Act
    duplicate.label = "https://b.example/v1"
    duplicate_hash = ContentHasher.hash({"value": duplicate})

    # Assert
    assert duplicate_hash != original_hash
    assert ContentHasher.hash({"value": original}) == original_hash


def test_instance_without_a_dict_refuses_with_a_fresh_token_per_read() -> None:
    # Arrange — unreachable for a real subclass (this mixin has no __slots__),
    # so the fallback is exercised directly on a slotted object.
    value = Slotted()

    # Act
    tokens = {PirnOpaqueValue._pirn_instance_identity_token(value) for _ in range(5)}  # type: ignore[arg-type]

    # Assert — it never matches anything, itself included.
    assert len(tokens) == 5


def _one_address(_value: object) -> int:
    """Stand-in for ``id``: every object reports the same address."""
    return 0x7F00_0000_1000


def _report_one_address_for_every_object(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the identity machinery see every object at one address.

    ``id`` is resolved as a module global before the builtin, so shadowing it
    in the two modules that call it simulates address reuse exactly, with no
    dependence on the allocator.
    """
    monkeypatch.setattr(pirn_identity_nonce_module, "id", _one_address, raising=False)
    monkeypatch.setattr(pirn_opaque_value_module, "id", _one_address, raising=False)


def _read_token_after_barrier(
    value: PirnOpaqueValue, barrier: threading.Barrier, seen: list[str]
) -> None:
    """Thread body: wait for every reader, then read the token once."""
    barrier.wait()
    seen.append(value._pirn_identity_token())
