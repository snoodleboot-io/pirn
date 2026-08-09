"""Unit tests for the canonical-JSON hashing seam (PIR-726 / WS8-A2).

The seam exists so the package has exactly one answer to "what bytes do we
hash?". Its acceptance criterion is negative: adopting it must move *nothing*
that is already persisted. The decisive test here is therefore
:meth:`TestCanonicalJsonReproducesDurableDigests.test_reproduces_the_pinned_checkpoint_digest`
— the seam must reproduce the golden checkpoint digest byte for byte.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, ClassVar

import pytest

from pirn_agents.determinism.content_digest import content_digest
from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy
from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
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


def _golden_state() -> RunState:
    """Return the same fixed state pinned by ``test_checkpoint_hash_invariant``."""
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
    """The seam must not move anything already written to storage."""

    # Restated from tests/sessions/test_checkpoint_hash_invariant.py on purpose:
    # if the seam and the checkpoint hasher ever disagree, one of these two
    # files fails, and the disagreement cannot pass CI unnoticed.
    _golden_checkpoint_digest = "9e638e5c7315150eb97518e4441423cf3e1aafbf24b06db203198b27c8d39f94"

    def test_reproduces_the_pinned_checkpoint_digest(self) -> None:
        assert CanonicalJson.digest(_golden_state().to_payload()) == (
            self._golden_checkpoint_digest
        ), (
            "The seam does not agree with the persisted checkpoint format. "
            "Adopting it would orphan every stored checkpoint_id."
        )

    def test_agrees_with_the_checkpoint_hasher(self) -> None:
        state = _golden_state()
        assert CanonicalJson.digest(state.to_payload()) == RunCheckpoint.content_hash(state)

    @pytest.mark.parametrize("name", _payload_names())
    def test_agrees_with_content_digest_on_json_payloads(self, name: str) -> None:
        # content_digest keys every cassette entry; the seam must be a drop-in.
        assert CanonicalJson.digest(_payloads()[name]) == content_digest(_payloads()[name])


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
