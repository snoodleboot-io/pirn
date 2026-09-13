"""Golden lock on the checkpoint content hash (PIR-706 / WS6-S3).

``RunCheckpoint.content_hash`` is a digest over ``state.to_payload()``, and
``checkpoint_id`` IS that digest. Every checkpoint ever persisted is keyed by
it, so the payload is a **storage format**, not an internal detail:

* adding, removing or renaming a key in ``RunState.to_payload()`` (or in any
  nested ``SessionMessage`` / ``SessionToolResult`` / ``ExecutionCursor``
  payload),
* changing how a value is rendered (``None`` -> ``"None"``, tuple -> list,
  int -> str, an enum member -> its ``.value``),
* or swapping the canonicalisation

all move the digest, which silently orphans every stored checkpoint and breaks
resume: a re-created checkpoint gets a NEW id, the old row is never found
again, and the run restarts from scratch instead of resuming.

This module pins the digest of one fixed state to hard-coded literals so any
such change fails here, loudly and in one obvious place, instead of in
production. **If a test here fails, the fix is almost never to update the
literal** — it is to revert whatever changed the payload.

The one sanctioned exception, already taken: ADR "agents speaks core" WS3 part
2 moved the *algorithm* itself, from
``pirn_agents.serialization.canonical_json.CanonicalJson.digest`` (bare
64-hex SHA-256, ``format_version=1``) to core's
``pirn.core.hashing.content_hash`` (``"sha256:"``-prefixed,
``format_version=2``, the same canonicaliser every other pirn domain's
lineage hashing uses) — a deliberate, versioned storage-format break with a
migration path (:meth:`RunCheckpoint.migrate_v1_to_v2`), not a silent
literal update: ``TestCheckpointHashV1Invariant`` below still pins the
original v1 digest exactly, byte for byte, and :meth:`from_payload` still
reads an unmarked (pre-migration) persisted payload as v1.

The fixture is built from literals inside this file rather than from
``tests/sessions/conftest.py``, so that editing a shared factory cannot quietly
move the golden value.
"""

from __future__ import annotations

import hashlib
import json
import warnings

from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_tool_result import SessionToolResult


def _golden_state() -> RunState:
    """Return the fixed run state whose digest this module pins.

    Deliberately exercises every payload branch: two messages, a
    multi-step plan, a partially advanced cursor, a tool result with a
    nested mapping output, and a tool result whose output is ``None``.
    """
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


def _quietly(*args, **kwargs) -> RunCheckpoint:
    """Build a ``RunCheckpoint``, expecting (not silencing evidence of) its deprecation warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return RunCheckpoint.create(*args, **kwargs)


class TestCheckpointHashV1Invariant:
    """The legacy (pre-ADR) checkpoint content hash must never drift."""

    # The canonical JSON the v1 digest is taken over. Pinned separately from
    # the digest so a failure says WHICH part of the payload moved, not just
    # "the hash changed".
    _golden_canonical = (
        '{"cursor":{"completed_steps":["plan-a"],"step_index":1},'
        '"messages":[{"content":"hi","role":"user"},'
        '{"content":"hello","role":"assistant"}],'
        '"plan":["plan-a","plan-b","plan-c"],'
        '"session_id":"sess-fixed",'
        '"tool_results":[{"call_id":"c1","output":{"hits":2},"tool_name":"search"},'
        '{"call_id":"c2","output":null,"tool_name":"calc"}]}'
    )
    _golden_digest = "9e638e5c7315150eb97518e4441423cf3e1aafbf24b06db203198b27c8d39f94"

    def test_canonical_payload_json_is_unchanged(self) -> None:
        canonical = json.dumps(_golden_state().to_payload(), sort_keys=True, separators=(",", ":"))
        assert canonical == self._golden_canonical, (
            "RunState.to_payload() changed shape. This is the persisted "
            "checkpoint format -- every stored checkpoint_id is derived from "
            "it. Revert the payload change, or ship a checkpoint migration."
        )

    def test_content_hash_matches_golden_digest(self) -> None:
        digest = RunCheckpoint.content_hash(_golden_state(), format_version=1)
        assert digest == self._golden_digest, (
            "RunCheckpoint.content_hash(format_version=1) drifted: previously "
            "persisted checkpoints can no longer be found by id."
        )

    def test_checkpoint_id_matches_golden_digest(self) -> None:
        checkpoint = _quietly(_golden_state(), format_version=1)
        assert checkpoint.checkpoint_id == self._golden_digest

    def test_digest_is_sha256_of_the_canonical_json(self) -> None:
        # Pins the ALGORITHM and the encoding, not just the output: swapping
        # sha256 for another hash, or utf-8 for another codec, fails here.
        expected = hashlib.sha256(self._golden_canonical.encode("utf-8")).hexdigest()
        assert expected == self._golden_digest
        assert RunCheckpoint.content_hash(_golden_state(), format_version=1) == expected

    def test_hash_is_stable_across_repeated_calls(self) -> None:
        digests = {RunCheckpoint.content_hash(_golden_state(), format_version=1) for _ in range(5)}
        assert digests == {self._golden_digest}

    def test_checkpoint_round_trips_under_the_pinned_id(self) -> None:
        checkpoint = _quietly(_golden_state(), format_version=1)
        restored = RunCheckpoint.from_payload(checkpoint.to_payload())
        assert restored.checkpoint_id == self._golden_digest
        assert restored.format_version == 1
        assert RunCheckpoint.content_hash(restored.state, format_version=1) == self._golden_digest

    def test_from_payload_without_format_version_reads_as_v1(self) -> None:
        """An already-persisted (pre-migration) payload has no format_version key at all."""
        legacy_payload = {
            "checkpoint_id": self._golden_digest,
            "state": _golden_state().to_payload(),
        }
        restored = RunCheckpoint.from_payload(legacy_payload)
        assert restored.format_version == 1


class TestCheckpointHashV2Invariant:
    """The current (ADR WS3 part 2) checkpoint content hash must never drift."""

    _golden_digest = "sha256:a2d01bf759b46001526313b62fb1c652cc2fffe34383aa09fc03c8a0672cbdca"

    def test_content_hash_matches_golden_digest(self) -> None:
        assert RunCheckpoint.content_hash(_golden_state()) == self._golden_digest

    def test_create_defaults_to_v2(self) -> None:
        checkpoint = _quietly(_golden_state())
        assert checkpoint.format_version == 2
        assert checkpoint.checkpoint_id == self._golden_digest

    def test_round_trips_with_format_version_preserved(self) -> None:
        checkpoint = _quietly(_golden_state())
        restored = RunCheckpoint.from_payload(checkpoint.to_payload())
        assert restored.format_version == 2
        assert restored.checkpoint_id == self._golden_digest


class TestMigrateV1ToV2:
    def test_migrates_a_v1_checkpoint_to_v2(self) -> None:
        v1 = _quietly(_golden_state(), format_version=1)
        v2 = RunCheckpoint.migrate_v1_to_v2(v1)
        assert v2.format_version == 2
        assert v2.checkpoint_id == TestCheckpointHashV2Invariant._golden_digest
        assert v2.state == v1.state

    def test_refuses_to_migrate_an_already_v2_checkpoint(self) -> None:
        v2 = _quietly(_golden_state())
        try:
            RunCheckpoint.migrate_v1_to_v2(v2)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")

    def test_rejects_non_checkpoint(self) -> None:
        try:
            RunCheckpoint.migrate_v1_to_v2("not a checkpoint")  # type: ignore[arg-type]
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError")


class TestCheckpointHashSensitivity:
    """The digest must actually MOVE when the state does (current default: v2).

    Without these, a ``content_hash`` accidentally reduced to a constant
    would still satisfy the golden-value tests above.
    """

    def test_a_changed_message_changes_the_id(self) -> None:
        mutated = _golden_state().with_message(SessionMessage(role="user", content="more"))
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashV2Invariant._golden_digest

    def test_a_changed_cursor_changes_the_id(self) -> None:
        base = _golden_state()
        mutated = RunState(
            session_id=base.session_id,
            messages=base.messages,
            plan=base.plan,
            tool_results=base.tool_results,
            cursor=ExecutionCursor(step_index=2, completed_steps=("plan-a", "plan-b")),
        )
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashV2Invariant._golden_digest

    def test_a_changed_tool_result_changes_the_id(self) -> None:
        base = _golden_state()
        mutated = RunState(
            session_id=base.session_id,
            messages=base.messages,
            plan=base.plan,
            tool_results=(SessionToolResult(call_id="c1", tool_name="search", output={"hits": 3}),),
            cursor=base.cursor,
        )
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashV2Invariant._golden_digest

    def test_a_changed_session_id_changes_the_id(self) -> None:
        base = _golden_state()
        mutated = RunState(
            session_id="sess-other",
            messages=base.messages,
            plan=base.plan,
            tool_results=base.tool_results,
            cursor=base.cursor,
        )
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashV2Invariant._golden_digest
