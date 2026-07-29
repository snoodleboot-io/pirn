"""Golden lock on the checkpoint content hash (PIR-706 / WS6-S3).

``RunCheckpoint.content_hash`` is a SHA-256 over
``json.dumps(state.to_payload(), sort_keys=True, separators=(",", ":"))``, and
``checkpoint_id`` IS that digest. Every checkpoint ever persisted is keyed by
it, so the payload is a **storage format**, not an internal detail:

* adding, removing or renaming a key in ``RunState.to_payload()`` (or in any
  nested ``SessionMessage`` / ``SessionToolResult`` / ``ExecutionCursor``
  payload),
* changing how a value is rendered (``None`` -> ``"None"``, tuple -> list,
  int -> str, an enum member -> its ``.value``),
* or swapping the canonicalisation (dropping ``sort_keys``, changing the
  separators)

all move the digest, which silently orphans every stored checkpoint and breaks
resume: a re-created checkpoint gets a NEW id, the old row is never found
again, and the run restarts from scratch instead of resuming.

This module pins the digest of one fixed state to a hard-coded literal so any
such change fails here, loudly and in one obvious place, instead of in
production. **If this test fails, the fix is almost never to update the
literal** -- it is to revert whatever changed the payload. Updating the literal
is a deliberate storage-format break that needs a migration for existing
checkpoints.

The fixture is built from literals inside this file rather than from
``tests/sessions/conftest.py``, so that editing a shared factory cannot quietly
move the golden value.
"""

from __future__ import annotations

import hashlib
import json

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


class TestCheckpointHashInvariant:
    """The persisted-checkpoint content hash must never drift."""

    # The canonical JSON the digest is taken over. Pinned separately from the
    # digest so a failure says WHICH part of the payload moved, not just "the
    # hash changed".
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
        assert RunCheckpoint.content_hash(_golden_state()) == self._golden_digest, (
            "RunCheckpoint.content_hash drifted: previously persisted "
            "checkpoints can no longer be found by id, so resume breaks."
        )

    def test_checkpoint_id_matches_golden_digest(self) -> None:
        assert RunCheckpoint.create(_golden_state()).checkpoint_id == self._golden_digest

    def test_digest_is_sha256_of_the_canonical_json(self) -> None:
        # Pins the ALGORITHM and the encoding, not just the output: swapping
        # sha256 for another hash, or utf-8 for another codec, fails here.
        expected = hashlib.sha256(self._golden_canonical.encode("utf-8")).hexdigest()
        assert expected == self._golden_digest
        assert RunCheckpoint.content_hash(_golden_state()) == expected

    def test_hash_is_stable_across_repeated_calls(self) -> None:
        digests = {RunCheckpoint.content_hash(_golden_state()) for _ in range(5)}
        assert digests == {self._golden_digest}

    def test_equal_states_share_an_id_so_dedup_works(self) -> None:
        assert RunCheckpoint.create(_golden_state()).checkpoint_id == (
            RunCheckpoint.create(_golden_state()).checkpoint_id
        )

    def test_checkpoint_round_trips_under_the_pinned_id(self) -> None:
        checkpoint = RunCheckpoint.create(_golden_state())
        restored = RunCheckpoint.from_payload(checkpoint.to_payload())
        assert restored.checkpoint_id == self._golden_digest
        assert RunCheckpoint.content_hash(restored.state) == self._golden_digest


class TestCheckpointHashSensitivity:
    """The digest must actually MOVE when the state does.

    Without these, a ``content_hash`` accidentally reduced to a constant
    would still satisfy the golden-value tests above.
    """

    def test_a_changed_message_changes_the_id(self) -> None:
        mutated = _golden_state().with_message(SessionMessage(role="user", content="more"))
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashInvariant._golden_digest

    def test_a_changed_cursor_changes_the_id(self) -> None:
        base = _golden_state()
        mutated = RunState(
            session_id=base.session_id,
            messages=base.messages,
            plan=base.plan,
            tool_results=base.tool_results,
            cursor=ExecutionCursor(step_index=2, completed_steps=("plan-a", "plan-b")),
        )
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashInvariant._golden_digest

    def test_a_changed_tool_result_changes_the_id(self) -> None:
        base = _golden_state()
        mutated = RunState(
            session_id=base.session_id,
            messages=base.messages,
            plan=base.plan,
            tool_results=(SessionToolResult(call_id="c1", tool_name="search", output={"hits": 3}),),
            cursor=base.cursor,
        )
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashInvariant._golden_digest

    def test_a_changed_session_id_changes_the_id(self) -> None:
        base = _golden_state()
        mutated = RunState(
            session_id="sess-other",
            messages=base.messages,
            plan=base.plan,
            tool_results=base.tool_results,
            cursor=base.cursor,
        )
        assert RunCheckpoint.content_hash(mutated) != TestCheckpointHashInvariant._golden_digest
