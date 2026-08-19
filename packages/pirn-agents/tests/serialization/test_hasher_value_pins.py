"""Value pins on the remaining content-addressed hashers (PIR-726 / WS8-A4).

``IdempotencyKeyAssigner.assign`` and ``AgentKnotIdFactory.derive`` each hash a
canonical JSON encoding, and neither had a single pinned output value — so a
change to their canonicalisation would have moved every key they produce with
the whole suite still green. Both outputs escape the process:

* An idempotency key is sent to a backend so it can dedupe a retried mutation.
  If the key moves between the original call and the retry, the backend sees a
  new operation and the mutation is applied twice.
* A knot id lands in lineage records and aligns generated graphs with the
  engine's content-addressed cache. If it moves, unchanged graphs lose their
  cache entries and their lineage continuity.

These pins were recorded *before* the hashers were moved onto
:class:`~pirn_agents.serialization.canonical_json.CanonicalJson`, so they prove
the move was byte-identical rather than merely plausible.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from pirn_agents.builder.agent_knot_id_factory import AgentKnotIdFactory
from pirn_agents.resilience.idempotency_key_assigner import IdempotencyKeyAssigner
from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy


def _idempotency_calls() -> dict[str, tuple[str, dict[str, Any]]]:
    """Return the fixed (operation, arguments) matrix the key pins cover."""
    return {
        "no_args": ("charge", {}),
        "flat": ("charge", {"amount": 100, "currency": "usd"}),
        "unordered": ("charge", {"currency": "usd", "amount": 100}),
        "nested": ("charge", {"meta": {"z": 1, "a": [1, 2]}, "amount": 100}),
        "unicode": ("charge", {"note": "café 中"}),
        "literals": ("charge", {"f": False, "n": None, "t": True}),
    }


def _knot_derivations() -> dict[str, dict[str, Any]]:
    """Return the fixed derive() keyword matrix the id pins cover."""
    return {
        "minimal": {"pattern": "react"},
        "llm_only": {"pattern": "react", "llm": "prov.openai"},
        "full": {
            "pattern": "react",
            "llm": "prov.openai",
            "memory": "mem.buffer",
            "tools": ["tool.search", "tool.calc"],
            "options": {"max_steps": 5},
        },
        "with_components": {
            "pattern": "rag",
            "llm": "prov.openai",
            "components": {"embedder": "emb.local", "store": "store.chroma"},
        },
        "unicode_option": {"pattern": "react", "options": {"note": "café"}},
    }


class TestIdempotencyKeyPins:
    """A derived idempotency key must survive a retry, so it must never drift."""

    _pins: ClassVar[dict[str, str]] = {
        "no_args": "0d1a975269bd6e28bc859ad6d82af0b658c8f9ef2439f2f190cd379a3054c85d",
        "flat": "887b157b5f766f58e907fee41f6ef4b9096724023abef9e760758d097223109f",
        "unordered": "887b157b5f766f58e907fee41f6ef4b9096724023abef9e760758d097223109f",
        "nested": "27ce0ce439e47c73a01add8902ce908f843fa4957a1a0d1215246649a11b9a54",
        "unicode": "8babb184f82a7b8cada1fae6ba25fc8ab7d83fa1d1b0f73a3948c228a4a3c4bc",
        "literals": "6c28ad3db490d7981ee142fd7affc368bc81663a8fb89d4663e9cb3209f0b666",
    }

    @pytest.mark.parametrize("name", sorted(_idempotency_calls()))
    def test_derived_key_is_unchanged(self, name: str) -> None:
        operation, arguments = _idempotency_calls()[name]
        actual = IdempotencyKeyAssigner().assign(operation=operation, arguments=arguments)
        assert actual == self._pins[name], (
            "A derived idempotency key moved. A retry now presents a different "
            "key than the original call, so the backend will re-apply the "
            "mutation instead of deduping it."
        )

    def test_namespaced_key_is_unchanged(self) -> None:
        assert IdempotencyKeyAssigner(namespace="tenant-a").assign(
            operation="charge", arguments={"amount": 1}
        ) == ("tenant-a:fbe6e950a8b99ac65471c91a2bd37308420afe872ee664a7b636af67d976c4a2")

    def test_key_order_does_not_move_the_key(self) -> None:
        assert self._pins["flat"] == self._pins["unordered"]

    def test_derivation_uses_the_shared_canonical_form(self) -> None:
        # The assigner hashes {"operation": ..., "arguments": ...} under the
        # REPR policy; spelling that out here is what makes the collapse in
        # PIR-726 verifiable rather than asserted.
        operation, arguments = _idempotency_calls()["nested"]
        assert IdempotencyKeyAssigner().assign(
            operation=operation, arguments=arguments
        ) == CanonicalJson.digest(
            {"operation": operation, "arguments": arguments}, policy=OpaquePolicy.REPR
        )


class TestAgentKnotIdPins:
    """A generated knot id keys lineage records and engine cache entries."""

    _pins: ClassVar[dict[str, str]] = {
        "minimal": "agent.react.fa8c5a6156e8",
        "llm_only": "agent.react.35af7bdf9a07",
        "full": "agent.react.260b32caf467",
        "with_components": "agent.rag.38421bf92179",
        "unicode_option": "agent.react.2d766a4189d2",
    }

    @pytest.mark.parametrize("name", sorted(_knot_derivations()))
    def test_derived_id_is_unchanged(self, name: str) -> None:
        assert AgentKnotIdFactory.derive(**_knot_derivations()[name]) == self._pins[name], (
            "A generated knot id moved. Unchanged graphs lose their lineage "
            "continuity and their engine cache alignment."
        )

    def test_digest_is_the_first_twelve_hex_of_the_canonical_digest(self) -> None:
        # Pins the truncation as well as the canonicalisation: the factory
        # takes the shared 64-hex digest and slices it, rather than hashing
        # differently.
        signature: dict[str, Any] = {
            "pattern": "react",
            "llm": None,
            "memory": None,
            "tools": [],
            "options": {},
        }
        assert self._pins["minimal"].endswith(CanonicalJson.digest(signature)[:12])

    def test_components_key_is_absent_when_empty(self) -> None:
        # An always-present "components" key would change the canonical form
        # and move every id derived for the llm/memory/tools patterns.
        with_empty = AgentKnotIdFactory.derive(pattern="react", components={})
        assert with_empty == self._pins["minimal"]
