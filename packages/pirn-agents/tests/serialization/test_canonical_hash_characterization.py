"""Characterization pin on every sha256-over-canonical-JSON hasher (PIR-726 / WS8-A1).

The package hashes payloads to stable ids in several places, and each one grew
its own ``json.dumps`` call with its own flags. This module pins, for one fixed
payload matrix, **both** the canonical string each hasher serialises to and the
digest it takes over that string — so a change to any hasher's canonicalisation
shows up here as a concrete before/after string, not as an opaque hash flip.

Two distinct things are recorded:

* **The intended canonical form** — ``sort_keys=True,
  separators=(",", ":")``, ``ensure_ascii`` at its default, UTF-8, bare 64-hex
  output. This is what
  :meth:`~pirn_agents.sessions.run_checkpoint.RunCheckpoint.content_hash` and
  :func:`~pirn_agents.determinism.content_digest.content_digest` already
  produce, and it is the form the WS8 seam adopts. Its pins are *durable*:
  cassette keys and checkpoint ids are derived from it, so moving one of these
  values is a storage-format break needing a migration. See
  ``tests/sessions/test_checkpoint_hash_invariant.py``.

* **The divergences** — :func:`~pirn_agents.caching.content_address.content_address`
  uses default separators (``", "`` / ``": "``) and ``ensure_ascii=False``, so
  it disagrees with the other hashers on *every* non-trivial payload. Those
  pins are *characterization only*: they record today's behaviour so the WS8
  migration is visibly deliberate. ``content_address`` keys only in-memory
  caches (``ResultCache``, ``PromptCache``, ``EmbeddingCache``,
  ``SemanticResultCache``), so moving its digests persists nothing.

Payloads are built from literals inside this file rather than from a shared
factory, so that editing a fixture elsewhere cannot quietly move a golden value.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, ClassVar

import pytest

from pirn_agents.caching.content_address import content_address
from pirn_agents.determinism.content_digest import content_digest


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


class TestContentDigestCanonicalForm:
    """``content_digest`` already emits the intended canonical form.

    These pins are durable: cassette entries and trace events are keyed by
    them, so a failure here means recorded cassettes can no longer be replayed.
    """

    _pins: ClassVar[dict[str, tuple[str, str]]] = {
        "empty_dict": (
            "{}",
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        ),
        "empty_list": (
            "[]",
            "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        ),
        "scalar_str": (
            '"x"',
            "ba2df4903a2c14e86dc3bcca58911b44ac1d2514b7227bf6eb08cfb978f55a1b",
        ),
        "scalar_int": (
            "42",
            "73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049",
        ),
        "scalar_float": (
            "1.5",
            "9f29a130438b81170b92a42650f9a94291ecad60bd47af2a3886e75f7f728725",
        ),
        "scalar_true": (
            "true",
            "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        ),
        "scalar_none": (
            "null",
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ),
        "flat_dict": (
            '{"a":1,"b":2}',
            "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
        ),
        "nested_dict": (
            '{"outer":{"a":[1,2,{"k":"v"}],"z":1}}',
            "d63181f8d8de3e20a9d0350b43a3ec4f757d36de9ed9df731e4c2182d113d22e",
        ),
        "list_of_dicts": (
            '[{"a":2,"b":1},{"c":4,"d":3}]',
            "b7674d3bc235a66d417357c0c4e21e834e6d899b1535ccdd3c988e9ce73d2c3d",
        ),
        "unicode": (
            '{"caf\\u00e9":"\\u4e2d\\u6587","emoji":"\\ud83d\\ude42"}',
            "77316f762139d24e2bc22c705a1299e5314ef700fdb649d88971a7ad71936e0b",
        ),
        "floats": (
            '{"exp":1e+20,"half":1.5,"neg_zero":-0.0}',
            "322f49bd7e3e2777535fa2986badb116eb3dd56322a9aab994e18455315270ff",
        ),
        "bools_and_null": (
            '{"f":false,"n":null,"t":true}',
            "22e00dc2f7b01420f940fbdbfbdf34fa0667cc6500186495023ba37722cbd05e",
        ),
        "empty_containers_nested": (
            '{"d":{},"s":"","xs":[]}',
            "0972be14a7aadbc57996f22ce4b3603bbd578b14376bd622ae205663df366cae",
        ),
        "deep_nesting": (
            '{"a":{"b":{"c":{"d":[{"e":1}]}}}}',
            "18daf33e34321c2d2974d31798276c8b0932db7e0e602b31c535d39253b626e2",
        ),
    }

    @pytest.mark.parametrize("name", _payload_names())
    def test_canonical_string_is_unchanged(self, name: str) -> None:
        canonical, _ = self._pins[name]
        actual = json.dumps(_payloads()[name], sort_keys=True, separators=(",", ":"), default=str)
        assert actual == canonical, (
            f"content_digest's canonical form moved for {name!r}: recorded "
            "cassettes are keyed by this string and can no longer be replayed."
        )

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_unchanged(self, name: str) -> None:
        _, digest = self._pins[name]
        assert content_digest(_payloads()[name]) == digest

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_sha256_of_the_pinned_canonical_string(self, name: str) -> None:
        # Pins the algorithm and the encoding, not just the output.
        canonical, digest = self._pins[name]
        assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == digest

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_bare_64_hex(self, name: str) -> None:
        digest = content_digest(_payloads()[name])
        assert len(digest) == 64
        int(digest, 16)

    def test_mapping_key_order_does_not_move_the_digest(self) -> None:
        assert content_digest({"a": 1, "b": 2, "c": 3}) == content_digest({"c": 3, "a": 1, "b": 2})

    def test_nested_mapping_key_order_does_not_move_the_digest(self) -> None:
        assert content_digest({"o": {"z": 1, "a": 2}}) == content_digest({"o": {"a": 2, "z": 1}})

    def test_list_order_does_move_the_digest(self) -> None:
        # Sequences are ordered data, not sets: reordering them is a real change.
        assert content_digest([1, 2]) != content_digest([2, 1])

    def test_non_json_leaf_currently_falls_back_to_str(self) -> None:
        # Characterization only. The WS8 seam's default policy is RAISE; this
        # records what `default=str` does today so the migration is visible.
        assert content_digest({"leaf": {1, 2}}) == content_digest({"leaf": str({1, 2})})


class TestContentAddressCanonicalForm:
    """``content_address`` diverges: default separators plus ``ensure_ascii=False``.

    Characterization only — these pins record the pre-WS8 behaviour. Nothing
    persisted is keyed by them (all four callers are in-memory caches).
    """

    _pins: ClassVar[dict[str, tuple[str, str]]] = {
        "empty_dict": (
            "{}",
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        ),
        "empty_list": (
            "[]",
            "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        ),
        "scalar_str": (
            '"x"',
            "ba2df4903a2c14e86dc3bcca58911b44ac1d2514b7227bf6eb08cfb978f55a1b",
        ),
        "scalar_int": (
            "42",
            "73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049",
        ),
        "scalar_float": (
            "1.5",
            "9f29a130438b81170b92a42650f9a94291ecad60bd47af2a3886e75f7f728725",
        ),
        "scalar_true": (
            "true",
            "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        ),
        "scalar_none": (
            "null",
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ),
        "flat_dict": (
            '{"a": 1, "b": 2}',
            "d8497d9d82770a70729261095aa98f7ef5154d7af499f8037b6ca250296785a6",
        ),
        "nested_dict": (
            '{"outer": {"a": [1, 2, {"k": "v"}], "z": 1}}',
            "daa1de7fddb9e6c634212d75b0d336a35cf66aeb95700e126af40ec054097535",
        ),
        "list_of_dicts": (
            '[{"a": 2, "b": 1}, {"c": 4, "d": 3}]',
            "84ed7b4eeb25e1b309496497adc5b5d802f94424808f309b217fd6559a270ae0",
        ),
        "unicode": (
            '{"café": "中文", "emoji": "🙂"}',
            "7774316c57c6934ff2fda500d09f4054cde7b1051e579aa87807a378f29f1a69",
        ),
        "floats": (
            '{"exp": 1e+20, "half": 1.5, "neg_zero": -0.0}',
            "d2e0f728806b8bb256e439ac82c2301f400fe8df7d8f47d7cf4bcc8c4c1bf56f",
        ),
        "bools_and_null": (
            '{"f": false, "n": null, "t": true}',
            "f555ff7fdba4f36070eecba4785bec7202ddba683c26ac7d346fe6d88addca9c",
        ),
        "empty_containers_nested": (
            '{"d": {}, "s": "", "xs": []}',
            "4bc9354bc53f4603eb23e2f0ca489881cf99f015fe43f68f6d9e155cabfe40b3",
        ),
        "deep_nesting": (
            '{"a": {"b": {"c": {"d": [{"e": 1}]}}}}',
            "28cde3eb4a7903c8e92cca5585e5e10b1005ba664b9e21be149ea4b70e540fc6",
        ),
    }

    @pytest.mark.parametrize("name", _payload_names())
    def test_canonical_string_is_unchanged(self, name: str) -> None:
        canonical, _ = self._pins[name]
        actual = json.dumps(_payloads()[name], sort_keys=True, default=repr, ensure_ascii=False)
        assert actual == canonical

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_unchanged(self, name: str) -> None:
        _, digest = self._pins[name]
        assert content_address(_payloads()[name]) == digest

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_sha256_of_the_pinned_canonical_string(self, name: str) -> None:
        canonical, digest = self._pins[name]
        assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == digest

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_bare_64_hex(self, name: str) -> None:
        digest = content_address(_payloads()[name])
        assert len(digest) == 64
        int(digest, 16)

    def test_mapping_key_order_does_not_move_the_digest(self) -> None:
        assert content_address({"a": 1, "b": 2, "c": 3}) == content_address(
            {"c": 3, "a": 1, "b": 2}
        )


class TestCanonicalFormDivergence:
    """Where the hashers agree today, and where they do not.

    The split is one-against-many: ``content_digest`` and
    ``RunCheckpoint.content_hash`` are byte-identical for every JSON payload,
    and ``content_address`` is the outlier.
    """

    def test_the_two_hashers_agree_only_on_separator_free_payloads(self) -> None:
        # Scalars and empty containers have no separators and no non-ASCII, so
        # the flag differences cannot show. Everything else diverges.
        agreeing = {
            name
            for name, payload in _payloads().items()
            if content_address(payload) == content_digest(payload)
        }
        assert agreeing == {
            "empty_dict",
            "empty_list",
            "scalar_str",
            "scalar_int",
            "scalar_float",
            "scalar_true",
            "scalar_none",
        }

    def test_separator_divergence_witness(self) -> None:
        assert content_address({"a": 1}) != content_digest({"a": 1})
        assert json.dumps({"a": 1}, sort_keys=True, default=repr, ensure_ascii=False) == '{"a": 1}'
        assert json.dumps({"a": 1}, sort_keys=True, separators=(",", ":")) == '{"a":1}'

    def test_ensure_ascii_divergence_witness(self) -> None:
        # Not just separators: content_address also escapes non-ASCII
        # differently, so an ASCII-only test suite would miss this one.
        payload = {"k": "café"}
        assert json.dumps(payload, sort_keys=True, ensure_ascii=False) == '{"k": "café"}'
        assert json.dumps(payload, sort_keys=True) == '{"k": "caf\\u00e9"}'

    def test_content_digest_and_checkpoint_hash_share_one_canonical_form(self) -> None:
        # The only difference between the two is the opaque-leaf branch
        # (`default=str` vs no default at all), which never fires on JSON data.
        for payload in _payloads().values():
            with_default = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            without_default = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            assert with_default == without_default

    def test_opaque_leaf_is_the_only_behavioural_split(self) -> None:
        # content_digest stringifies, the checkpoint hasher raises.
        leaf = {"leaf": object()}
        assert len(content_digest(leaf)) == 64
        with pytest.raises(TypeError):
            json.dumps(leaf, sort_keys=True, separators=(",", ":"))
