"""Value pins on :meth:`ContentDigest.digest` — the record/replay key (PIR-872).

``ContentDigest.digest`` is core's :meth:`pirn.core.content_hasher.ContentHasher.hash` in
``strict`` mode. Cassette entries and trace events are keyed by it, so this
module pins, for one fixed payload matrix, the exact digest each payload hashes
to — a change to core's canonicalisation shows up here as a concrete value
flip rather than as silently unreplayable cassettes.

Payloads are built from literals inside this file rather than from a shared
factory, so that editing a fixture elsewhere cannot quietly move a golden value.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pirn.core.content_hasher import ContentHasher
from pirn.exceptions.unhashable_value_error import UnhashableValueError

from pirn_agents.determinism.content_digest import ContentDigest


def _payloads() -> dict[str, Any]:
    """Return the fixed payload matrix every pin below is taken over.

    Deliberately spans the JSON type lattice and the shapes canonicalisation
    flags actually discriminate: mapping key order, nesting, non-ASCII text,
    float rendering, the three literals, and empty containers.
    """
    return {
        "empty_dict": {},
        "empty_list": [],
        "scalar_str": "x",
        "scalar_int": 42,
        "scalar_float": 1.5,
        "scalar_true": True,
        "scalar_none": None,
        "flat_dict": {"b": 2, "a": 1},
        "nested_dict": {"outer": {"z": 1, "a": [1, 2, {"k": "v"}]}},
        "list_of_dicts": [{"b": 1, "a": 2}, {"d": 3, "c": 4}],
        "unicode": {"café": "中文", "emoji": "🙂"},
        "floats": {"exp": 1e20, "half": 1.5, "neg_zero": -0.0},
        "bools_and_null": {"f": False, "n": None, "t": True},
        "empty_containers_nested": {"d": {}, "s": "", "xs": []},
        "deep_nesting": {"a": {"b": {"c": {"d": [{"e": 1}]}}}},
    }


def _payload_names() -> list[str]:
    """Return the matrix keys, sorted, for stable parametrisation ids."""
    return sorted(_payloads())


class _Canonical:
    """A leaf that declares its content form through ``__pirn_canonical__``."""

    def __init__(self, amount: int) -> None:
        self.amount = amount

    def __pirn_canonical__(self) -> dict[str, int]:
        return {"amount": self.amount}


class TestContentDigestPins:
    """``ContentDigest.digest`` emits ``ContentHasher.hash``'s strict canonical form."""

    _pins: ClassVar[dict[str, str]] = {
        "empty_dict": "sha256:1f722262a9334201ce5659c53b547a41ff19d504551da5bc907577a0c2286256",
        "empty_list": "sha256:5f3a40a2517a4e5f4658888c0a2839e5f60cbd0f8f4b654d6863d21ffbc01c73",
        "scalar_str": "sha256:ba2df4903a2c14e86dc3bcca58911b44ac1d2514b7227bf6eb08cfb978f55a1b",
        "scalar_int": "sha256:73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049",
        "scalar_float": "sha256:9f29a130438b81170b92a42650f9a94291ecad60bd47af2a3886e75f7f728725",
        "scalar_true": "sha256:b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "scalar_none": "sha256:74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "flat_dict": "sha256:1a1cb49cdfe2f23d37c744ca222e2fc700318f08b614e98033b0bdec14f2730a",
        "nested_dict": "sha256:eee0e7952ee4285976bdfdde7b2e1693b98353e6954634d417fc3efea9232873",
        "list_of_dicts": "sha256:5836e99bd755339269257278b4fe923338cd8af6c6376645a35b634fb5cbd683",
        "unicode": "sha256:75d7dbc67bbff3b5a868ccb3b8bfe2772f1eae07e833cae2cb425781a6e4ec17",
        "floats": "sha256:f085c1d7a525ccbf89c7228eb53c508b0f3f1a8586a5deade92680cdd75c369f",
        "bools_and_null": "sha256:6dff6c9e91c9ecf5d2790fe36961a98dd95fb9fa2491b36f61bceac405e9001f",
        "empty_containers_nested": (
            "sha256:e1b627801d6c1e4d42db23d0d61144803a70e8afb588398f86cf7ed7e851afc7"
        ),
        "deep_nesting": "sha256:c8c6ad97ce24c54dd12cc395c7ae67ab78f703c2c2e6592fc5c585458a080380",
    }

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_pinned(self, name: str) -> None:
        assert ContentDigest.digest(_payloads()[name]) == self._pins[name]

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_the_strict_content_hash(self, name: str) -> None:
        payload = _payloads()[name]
        assert ContentDigest.digest(payload) == ContentHasher.hash(payload, strict=True)

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_sha256_prefixed(self, name: str) -> None:
        digest = ContentDigest.digest(_payloads()[name])
        assert digest.startswith("sha256:")
        int(digest.removeprefix("sha256:"), 16)

    def test_mapping_key_order_does_not_move_the_digest(self) -> None:
        assert ContentDigest.digest({"a": 1, "b": 2, "c": 3}) == ContentDigest.digest(
            {"c": 3, "a": 1, "b": 2}
        )

    def test_nested_mapping_key_order_does_not_move_the_digest(self) -> None:
        assert ContentDigest.digest({"o": {"z": 1, "a": 2}}) == ContentDigest.digest(
            {"o": {"a": 2, "z": 1}}
        )

    def test_list_order_does_move_the_digest(self) -> None:
        # Sequences are ordered data, not sets: reordering them is a real change.
        assert ContentDigest.digest([1, 2]) != ContentDigest.digest([2, 1])

    def test_identity_keyed_opaque_leaf_is_refused(self) -> None:
        # PIR-785: a leaf whose only rendering is its memory address could
        # never replay, so it is refused at record time.
        with pytest.raises(UnhashableValueError):
            ContentDigest.digest({"leaf": object()})

    def test_leaf_declaring_its_canonical_form_is_accepted(self) -> None:
        assert ContentDigest.digest({"leaf": _Canonical(5)}) == ContentDigest.digest(
            {"leaf": _Canonical(5)}
        )
        assert ContentDigest.digest({"leaf": _Canonical(5)}) != ContentDigest.digest(
            {"leaf": _Canonical(6)}
        )
