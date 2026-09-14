"""Unit tests for the canonical-JSON hashing seam (PIR-726 / WS8-A2).

The seam exists so the package has exactly one answer to "what bytes do we
hash?". Its acceptance criterion is negative: adopting it must move *nothing*
that is already persisted. The decisive test here is therefore
:meth:`TestCanonicalJsonReproducesDurableDigests.test_reproduces_the_pinned_digest`
— the seam's own digest algorithm must never silently drift.
"""

from __future__ import annotations

import datetime
import decimal
import enum
import hashlib
import json
import pathlib
import uuid
from typing import Any, ClassVar

import pytest

from pirn_agents.determinism.content_digest import ContentDigest
from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy
from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_tool_result import SessionToolResult


def _payloads() -> dict[str, Any]:
    """Return a JSON payload matrix spanning the shapes canonicalisation affects."""
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


class _ContentRepr:
    """A leaf with a content-derived ``__repr__`` — the case that must keep working."""

    def __init__(self, v: int) -> None:
        self.v = v

    def __repr__(self) -> str:
        return f"_ContentRepr({self.v})"


class _Shade(enum.Enum):
    RED = "red"


def _stable_opaque_leaves() -> dict[str, Any]:
    """Return leaves JSON cannot encode but whose rendering *is* content-derived.

    These are the values ``STR``/``REPR`` already hashed reproducibly, and that
    the ``*_CONTENT`` narrowing must therefore leave byte-identical (PIR-795).
    """
    return {
        "datetime": datetime.datetime(2026, 1, 2, 3, 4, 5),
        "date": datetime.date(2026, 1, 2),
        "uuid": uuid.UUID(int=1),
        "decimal": decimal.Decimal("1.25"),
        "path": pathlib.PurePosixPath("/a/b"),
        "enum": _Shade.RED,
        "set": {1, 2},
        "bytes": b"abc",
        "custom_repr": _ContentRepr(7),
    }


def _stable_leaf_names() -> list[str]:
    """Return the stable-leaf keys, sorted, for stable parametrisation ids."""
    return sorted(_stable_opaque_leaves())


def _golden_state() -> RunState:
    """Return a fixed state exercising every ``RunState.to_payload()`` branch."""
    return RunState(
        session_id="sess-fixed",
        messages=(
            SessionMessage(role="user", content="hi"),
            SessionMessage(role="assistant", content="hello"),
        ),
        plan=("plan-a", "plan-b", "plan-c"),
        tool_results=(
            SessionToolResult(call_id="c1", tool_name="search", output={"hits": 2}),
            SessionToolResult(call_id="c2", tool_name="calc", output=None),
        ),
        cursor=ExecutionCursor(step_index=1, completed_steps=("plan-a",)),
    )


class TestCanonicalJsonReproducesDurableDigests:
    """The digest algorithm itself must not silently drift.

    ``RunCheckpoint`` (the original reason this golden value existed) was a
    one-cycle shim, now deleted (PIR-864); this pin now guards
    ``CanonicalJson.digest``'s own algorithm stability directly, since the
    deferred durable-key callers still listed in
    ``tests/test_core_vocabulary_ratchet.py`` (``content_digest.py``,
    ``idempotency_key_assigner.py``) depend on it never moving.
    """

    _golden_digest = "9e638e5c7315150eb97518e4441423cf3e1aafbf24b06db203198b27c8d39f94"

    def test_reproduces_the_pinned_digest(self) -> None:
        assert CanonicalJson.digest(_golden_state().to_payload()) == (self._golden_digest), (
            "CanonicalJson.digest's canonicalisation moved -- this orphans every durable caller."
        )

    @pytest.mark.parametrize("name", _payload_names())
    def test_agrees_with_content_digest_on_json_payloads(self, name: str) -> None:
        # content_digest keys every cassette entry; the seam must be a drop-in.
        assert CanonicalJson.digest(_payloads()[name]) == ContentDigest.digest(_payloads()[name])


class TestCanonicalJsonEncoding:
    """The one fixed canonical form: sorted keys, tight separators, UTF-8."""

    _canonical: ClassVar[dict[str, str]] = {
        "empty_dict": "{}",
        "empty_list": "[]",
        "scalar_str": '"x"',
        "scalar_int": "42",
        "scalar_float": "1.5",
        "scalar_true": "true",
        "scalar_none": "null",
        "flat_dict": '{"a":1,"b":2}',
        "nested_dict": '{"outer":{"a":[1,2,{"k":"v"}],"z":1}}',
        "list_of_dicts": '[{"a":2,"b":1},{"c":4,"d":3}]',
        "unicode": '{"caf\\u00e9":"\\u4e2d\\u6587","emoji":"\\ud83d\\ude42"}',
        "floats": '{"exp":1e+20,"half":1.5,"neg_zero":-0.0}',
        "bools_and_null": '{"f":false,"n":null,"t":true}',
        "empty_containers_nested": '{"d":{},"s":"","xs":[]}',
        "deep_nesting": '{"a":{"b":{"c":{"d":[{"e":1}]}}}}',
    }

    @pytest.mark.parametrize("name", _payload_names())
    def test_encode_matches_the_canonical_form(self, name: str) -> None:
        assert CanonicalJson.encode(_payloads()[name]) == self._canonical[name]

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_sha256_of_the_encoding(self, name: str) -> None:
        payload = _payloads()[name]
        expected = hashlib.sha256(CanonicalJson.encode(payload).encode("utf-8")).hexdigest()
        assert CanonicalJson.digest(payload) == expected

    @pytest.mark.parametrize("name", _payload_names())
    def test_digest_is_bare_64_hex(self, name: str) -> None:
        digest = CanonicalJson.digest(_payloads()[name])
        assert len(digest) == 64
        int(digest, 16)

    def test_mapping_keys_are_sorted(self) -> None:
        assert CanonicalJson.encode({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_key_order_does_not_move_the_digest(self) -> None:
        assert CanonicalJson.digest({"a": 1, "b": 2}) == CanonicalJson.digest({"b": 2, "a": 1})

    def test_nested_key_order_does_not_move_the_digest(self) -> None:
        assert CanonicalJson.digest({"o": {"z": 1, "a": 2}}) == (
            CanonicalJson.digest({"o": {"a": 2, "z": 1}})
        )

    def test_sequence_order_does_move_the_digest(self) -> None:
        assert CanonicalJson.digest([1, 2]) != CanonicalJson.digest([2, 1])

    def test_separators_are_tight(self) -> None:
        assert " " not in CanonicalJson.encode({"a": 1, "b": [1, 2]})

    def test_non_ascii_is_escaped(self) -> None:
        # ensure_ascii stays at its default. Flipping it to False would move
        # every cassette key whose payload contains non-ASCII text, while an
        # ASCII-only golden test stayed green -- a break that passes CI.
        assert CanonicalJson.encode({"k": "café"}) == '{"k":"caf\\u00e9"}'

    def test_encoding_is_utf8(self) -> None:
        payload = {"k": "café"}
        assert hashlib.sha256(
            CanonicalJson.encode(payload).encode("utf-8")
        ).hexdigest() == CanonicalJson.digest(payload)

    def test_digest_is_stable_across_repeated_calls(self) -> None:
        assert len({CanonicalJson.digest({"a": [1, {"b": 2}]}) for _ in range(5)}) == 1


class TestCanonicalJsonDeprecation:
    """ADR agents-speaks-core WS2: the class is a one-cycle shim, not deleted.

    The actual cut-over of ``digest`` to ``pirn.core.content_hasher.ContentHasher.hash`` is
    deferred (see the module docstring and the WS2 report) because three
    existing callers persist/transmit this exact bare-hex digest as a durable
    key. Until that migration lands, both methods keep their current bytes
    and only warn.
    """

    def test_encode_warns_deprecated(self) -> None:
        with pytest.warns(DeprecationWarning, match="CanonicalJson.encode"):
            CanonicalJson.encode({"a": 1})

    def test_digest_warns_deprecated(self) -> None:
        with pytest.warns(DeprecationWarning, match="CanonicalJson.digest"):
            CanonicalJson.digest({"a": 1})

    def test_digest_still_matches_sha256_of_encode_despite_the_warning(self) -> None:
        # The warning is informational only -- it must not change the bytes.
        with pytest.warns(DeprecationWarning):
            encoded = CanonicalJson.encode({"a": [1, {"b": 2}]})
        with pytest.warns(DeprecationWarning):
            digest = CanonicalJson.digest({"a": [1, {"b": 2}]})
        assert digest == hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def test_digest_emits_exactly_one_warning(self) -> None:
        # digest() shares its raw encoding step with encode() via a private
        # helper specifically so one public call emits one warning, not two.
        with pytest.warns(DeprecationWarning) as record:
            CanonicalJson.digest({"a": 1})
        assert len(record) == 1


class TestOpaquePolicy:
    """The opaque-leaf branch is explicit, and defaults to refusing."""

    def test_raise_is_the_default(self) -> None:
        with pytest.raises(TypeError):
            CanonicalJson.encode({"leaf": object()})

    def test_raise_policy_refuses_to_encode(self) -> None:
        with pytest.raises(TypeError):
            CanonicalJson.encode({"leaf": object()}, policy=OpaquePolicy.RAISE)

    def test_raise_policy_refuses_to_digest(self) -> None:
        with pytest.raises(TypeError):
            CanonicalJson.digest({"leaf": object()}, policy=OpaquePolicy.RAISE)

    def test_raise_names_the_offending_type(self) -> None:
        class Widget:
            pass

        with pytest.raises(TypeError, match="Widget"):
            CanonicalJson.encode({"leaf": Widget()})

    def test_repr_policy_stringifies_via_repr(self) -> None:
        assert CanonicalJson.encode({"leaf": {1, 2}}, policy=OpaquePolicy.REPR) == (
            json.dumps({"leaf": repr({1, 2})}, sort_keys=True, separators=(",", ":"))
        )

    def test_str_policy_stringifies_via_str(self) -> None:
        assert CanonicalJson.encode({"leaf": {1, 2}}, policy=OpaquePolicy.STR) == (
            json.dumps({"leaf": str({1, 2})}, sort_keys=True, separators=(",", ":"))
        )

    def test_policy_does_not_affect_pure_json_payloads(self) -> None:
        # The policy only selects the fallback branch; it must never change the
        # encoding of data that needed no fallback.
        for policy in OpaquePolicy:
            for payload in _payloads().values():
                assert CanonicalJson.encode(payload, policy=policy) == CanonicalJson.encode(payload)

    def test_policy_must_be_an_opaque_policy(self) -> None:
        with pytest.raises(TypeError):
            CanonicalJson.encode({"a": 1}, policy="repr")

    def test_repr_policy_keys_on_identity_for_default_objects(self) -> None:
        # Why RAISE is the default: repr() of an object without __repr__ embeds
        # its memory address, so the digest is an address, not a content hash.
        # CPython reuses freed addresses, which is the PIR-785 collision.
        class Bare:
            pass

        first = CanonicalJson.encode({"o": Bare()}, policy=OpaquePolicy.REPR)
        assert "0x" in first


class TestOpaquePolicyDefaultAuditDict:
    """``default_audit_dict`` — the ADR-aligned starting point for ``_pirn_audit_dict``."""

    def test_returns_a_type_tagged_content_dict(self) -> None:
        assert OpaquePolicy.default_audit_dict(decimal.Decimal("1.25")) == {
            "__type__": "Decimal",
            "repr": "Decimal('1.25')",
        }

    def test_two_equal_values_produce_equal_dicts(self) -> None:
        assert OpaquePolicy.default_audit_dict({1, 2}) == OpaquePolicy.default_audit_dict({2, 1})

    def test_refuses_a_value_with_no_content_derived_repr(self) -> None:
        class Bare:
            pass

        with pytest.raises(TypeError, match="memory address"):
            OpaquePolicy.default_audit_dict(Bare())

    def test_refuses_a_subclass_that_inherits_the_default_repr(self) -> None:
        class Bare:
            pass

        class Derived(Bare):
            pass

        with pytest.raises(TypeError):
            OpaquePolicy.default_audit_dict(Derived())


class TestContentOnlyPolicies:
    """``STR_CONTENT`` / ``REPR_CONTENT`` — PIR-795.

    These narrow ``STR`` / ``REPR`` to reject exactly the leaves that render a
    memory address, and nothing else. The load-bearing property is *negative*:
    adopting them must not move a single digest that was already stable, or
    tightening the two live key spaces would orphan cassettes and issued
    idempotency keys.
    """

    @pytest.mark.parametrize("name", _stable_leaf_names())
    def test_narrowing_does_not_move_a_stable_digest(self, name: str) -> None:
        # THE migration guarantee. If this ever fails, adopting the narrowed
        # policy became a storage break for cassettes / idempotency keys.
        payload = {"leaf": _stable_opaque_leaves()[name]}
        assert CanonicalJson.digest(
            payload, policy=OpaquePolicy.STR_CONTENT
        ) == CanonicalJson.digest(payload, policy=OpaquePolicy.STR)
        assert CanonicalJson.digest(
            payload, policy=OpaquePolicy.REPR_CONTENT
        ) == CanonicalJson.digest(payload, policy=OpaquePolicy.REPR)

    @pytest.mark.parametrize("policy", [OpaquePolicy.STR_CONTENT, OpaquePolicy.REPR_CONTENT])
    def test_refuses_a_leaf_that_renders_its_own_address(self, policy: OpaquePolicy) -> None:
        class Bare:
            pass

        with pytest.raises(TypeError, match="memory address"):
            CanonicalJson.digest({"leaf": Bare()}, policy=policy)

    @pytest.mark.parametrize("policy", [OpaquePolicy.STR_CONTENT, OpaquePolicy.REPR_CONTENT])
    def test_refusal_reaches_a_nested_leaf(self, policy: OpaquePolicy) -> None:
        class Bare:
            pass

        with pytest.raises(TypeError):
            CanonicalJson.digest({"a": [{"b": Bare()}]}, policy=policy)

    @pytest.mark.parametrize("policy", [OpaquePolicy.STR_CONTENT, OpaquePolicy.REPR_CONTENT])
    def test_refuses_a_subclass_that_inherits_the_default_repr(self, policy: OpaquePolicy) -> None:
        # The check must not be "does this exact class define __repr__" — a
        # subclass inherits the identity rendering just as surely.
        class Bare:
            pass

        class Derived(Bare):
            pass

        with pytest.raises(TypeError):
            CanonicalJson.digest({"leaf": Derived()}, policy=policy)

    def test_each_fallback_is_judged_on_what_it_actually_rendered(self) -> None:
        # A class defining __str__ but not __repr__ renders content under `str`
        # and identity under `repr`. Judging the rendered text rather than the
        # dunder is what lets one implementation serve both fallbacks.
        class StrOnly:
            def __str__(self) -> str:
                return "StrOnly!"

        payload = {"leaf": StrOnly()}
        assert CanonicalJson.digest(
            payload, policy=OpaquePolicy.STR_CONTENT
        ) == CanonicalJson.digest(payload, policy=OpaquePolicy.STR)
        with pytest.raises(TypeError):
            CanonicalJson.digest(payload, policy=OpaquePolicy.REPR_CONTENT)

    def test_str_and_repr_variants_stay_distinct(self) -> None:
        # Collapsing the two into one policy would move exactly the digests
        # this change exists to preserve: str(Decimal("1.25")) is "1.25" where
        # repr is "Decimal('1.25')".
        payload = {"leaf": decimal.Decimal("1.25")}
        assert CanonicalJson.digest(
            payload, policy=OpaquePolicy.STR_CONTENT
        ) != CanonicalJson.digest(payload, policy=OpaquePolicy.REPR_CONTENT)


class TestContentDigestRejectsIdentityKeyedRequests:
    """PIR-795 at the cassette seam — the failure must land at record time."""

    def test_a_request_carrying_an_identity_keyed_leaf_is_refused(self) -> None:
        # Previously this returned a 64-char digest derived from a memory
        # address, so the cassette recorded under it could never be replayed:
        # the next run computed a different key and simply missed. Refusing at
        # record time is what makes that discoverable.
        class Handle:
            pass

        with pytest.raises(TypeError, match="memory address"):
            ContentDigest.digest({"prompt": "hi", "handle": Handle()})

    @pytest.mark.parametrize("name", _stable_leaf_names())
    def test_a_request_carrying_a_content_rendering_leaf_still_digests(self, name: str) -> None:
        payload = {"prompt": "hi", "leaf": _stable_opaque_leaves()[name]}
        assert len(ContentDigest.digest(payload)) == 64

    @pytest.mark.parametrize("name", _stable_leaf_names())
    def test_recorded_digests_do_not_move(self, name: str) -> None:
        # The migration guarantee stated at the seam callers actually use.
        payload = {"prompt": "hi", "leaf": _stable_opaque_leaves()[name]}
        assert ContentDigest.digest(payload) == CanonicalJson.digest(
            payload, policy=OpaquePolicy.STR
        )
