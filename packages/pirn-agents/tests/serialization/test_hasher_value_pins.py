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

ADR agents-speaks-core WS2 part 2 (2026-09-13) intentionally moved the
:class:`~pirn_agents.resilience.idempotency_key_assigner.IdempotencyKeyAssigner`
pins: it now derives keys via :func:`pirn.core.hashing.content_hash` instead
of ``CanonicalJson``, a sanctioned, breaking format change (the ``sha256:``
prefix core emits IS the new format version — see that module's docstring
and "Idempotency keys" in ``docs/domains/agents.md`` for the operational
note). The pins below are the *post*-migration values, re-recorded from the
new algorithm, so this file keeps doing its job: catching any *further,
unintended* drift from here on.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from pirn_agents.builder.agent_knot_id_factory import AgentKnotIdFactory
from pirn_agents.resilience.idempotency_key_assigner import IdempotencyKeyAssigner


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
        "no_args": "sha256:68d593816f599ddb6029d5db366bb9f55c90e99dfff7a6b69198c0583c4f35ed",
        "flat": "sha256:4d031fac325465aa52f245adf4efc2b3f51462a1fb1bb6a9483e1c5b9622c70f",
        "unordered": "sha256:4d031fac325465aa52f245adf4efc2b3f51462a1fb1bb6a9483e1c5b9622c70f",
        "nested": "sha256:d0c2c343838cdbc5516c1c1aef6d44cd53aa476f0410cbc9ba71294fcbffd1ce",
        "unicode": "sha256:a525262ad80e05270f7f0a73834fa588b995b3d55b495c05662374f26642b3fc",
        "literals": "sha256:9db6e67fb965796153915a88268236b6161e1eec4936fdc0d51f95896abfa843",
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
        ) == ("tenant-a:sha256:9ac572bcde7e30fa2de4cbf3c921638895ab76fbb6cb1dbefda5c8491d7ead4d")

    def test_key_order_does_not_move_the_key(self) -> None:
        assert self._pins["flat"] == self._pins["unordered"]

    def test_derivation_uses_content_hash(self) -> None:
        # The assigner hashes {"operation": ..., "arguments": ...} through
        # content_hash directly for JSON-native arguments; spelling that out
        # here is what makes the ADR WS2 part 2 migration verifiable rather
        # than asserted.
        from pirn.core.hashing import content_hash

        operation, arguments = _idempotency_calls()["nested"]
        assert IdempotencyKeyAssigner().assign(operation=operation, arguments=arguments) == (
            content_hash({"operation": operation, "arguments": arguments}, strict=True)
        )


class TestAgentKnotIdPins:
    """A generated knot id keys lineage records and engine cache entries."""

    # ADR agents-speaks-core WS2 part 2 (2026-09-13) intentionally moved these
    # pins: AgentKnotIdFactory now digests via pirn.core.hashing.content_hash
    # instead of CanonicalJson (see that module's docstring and the
    # CHANGELOG). Re-recorded from the new algorithm.
    _pins: ClassVar[dict[str, str]] = {
        "minimal": "agent.react.fce3a462fd64",
        "llm_only": "agent.react.51704811bccf",
        "full": "agent.react.4c6352ea6988",
        "with_components": "agent.rag.ef2c0271996e",
        "unicode_option": "agent.react.1c7b47d57547",
    }

    @pytest.mark.parametrize("name", sorted(_knot_derivations()))
    def test_derived_id_is_unchanged(self, name: str) -> None:
        assert AgentKnotIdFactory.derive(**_knot_derivations()[name]) == self._pins[name], (
            "A generated knot id moved. Unchanged graphs lose their lineage "
            "continuity and their engine cache alignment."
        )

    def test_digest_is_the_first_twelve_hex_of_the_content_hash_digest(self) -> None:
        # Pins the truncation as well as the canonicalisation: the factory
        # takes content_hash's digest (minus its sha256: prefix) and slices
        # it, rather than hashing differently.
        from pirn.core.hashing import content_hash

        signature: dict[str, Any] = {
            "pattern": "react",
            "llm": None,
            "memory": None,
            "tools": [],
            "options": {},
        }
        expected_suffix = content_hash(signature, strict=True).removeprefix("sha256:")[:12]
        assert self._pins["minimal"].endswith(expected_suffix)

    def test_components_key_is_absent_when_empty(self) -> None:
        # An always-present "components" key would change the canonical form
        # and move every id derived for the llm/memory/tools patterns.
        with_empty = AgentKnotIdFactory.derive(pattern="react", components={})
        assert with_empty == self._pins["minimal"]
