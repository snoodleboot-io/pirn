"""Identity-keyed agents values never inherit a freed object's hash (PIR-852).

``Tool`` (by default) and every HTTP ``LLMProvider`` hash by instance identity.
When that identity was ``id()``, CPython handed a freed tool's or provider's
address to the next one built, which then hashed equal to it: a review measured
a ``StubTool`` colliding 292 of 300 times after ``gc.collect()``. Core now keys
on :meth:`~pirn.core.pirn_opaque_value.PirnOpaqueValue._pirn_identity_token`,
and these loops pin that for real pirn-agents classes, at the hash level and
through an end-to-end replay.

Each loop runs in a clean subprocess (:class:`IdentityReuseSubprocess`) and
asserts that addresses really were reused. Inside a large coverage-traced test
process CI saw no reuse at all, so an in-process loop could not exercise the
hazard, and a loop that stopped exercising it must fail rather than pass.
"""

from __future__ import annotations

from tests.tools.identity_reuse_subprocess import IdentityReuseSubprocess


def test_freed_stub_tool_hash_never_reappears_for_a_new_tool_at_its_address() -> None:
    # Arrange — free a StubTool, collect, build another; bare and in a list.

    # Act
    tally = IdentityReuseSubprocess.run("stub_tool_hash", 100)

    # Assert
    assert tally["reuses"] > 0, f"no address was reused; the loop tested nothing: {tally}"
    assert tally["collisions"] == 0, tally


def test_freed_provider_hash_never_reappears_for_a_new_provider_at_its_address() -> None:
    # Arrange — free an OpenAICompatibleProvider, collect, build one for another model.

    # Act
    tally = IdentityReuseSubprocess.run("provider_hash", 100)

    # Assert
    assert tally["reuses"] > 0, f"no address was reused; the loop tested nothing: {tally}"
    assert tally["collisions"] == 0, tally


def test_replay_never_serves_a_tool_built_after_the_recorded_one_was_freed() -> None:
    # Arrange — record a ToolInvocation with tool A, free it, replay with tool B.

    # Act
    tally = IdentityReuseSubprocess.run("tool_replay", 100)

    # Assert — a collision here means replay SERVED A's recorded result to B.
    assert tally["reuses"] > 0, f"no address was reused; the loop tested nothing: {tally}"
    assert tally["collisions"] == 0, tally
