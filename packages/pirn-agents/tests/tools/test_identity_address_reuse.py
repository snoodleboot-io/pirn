"""Identity-keyed agents values never inherit a freed object's hash (PIR-852).

``Tool`` (by default) and every HTTP ``LLMProvider`` hash by instance identity.
When that identity was ``id()``, CPython handed a freed tool's or provider's
address to the next one built, which then hashed equal to it: a review measured
a ``StubTool`` colliding 292 of 300 times after ``gc.collect()``. Core now keys
on :meth:`~pirn.core.pirn_opaque_value.PirnOpaqueValue._pirn_identity_token`,
and these loops pin that for real pirn-agents classes, at the hash level and
through an end-to-end replay.

Each loop asserts that addresses really were reused, so a loop that stopped
exercising the hazard fails instead of passing vacuously. ``gc.freeze()`` keeps
each full collection to the objects the loop created.
"""

from __future__ import annotations

import gc

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.hashing import content_hash
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation


def test_freed_stub_tool_hash_never_reappears_for_a_new_tool_at_its_address() -> None:
    # Arrange
    iterations = 250
    reuses = 0
    collisions = 0

    # Act
    gc.freeze()
    try:
        for _ in range(iterations):
            freed = StubTool(result="recorded")
            freed_address = id(freed)
            freed_hash = content_hash({"tool": freed})
            freed_list_hash = content_hash({"tools": [freed]})
            del freed
            gc.collect()
            fresh = StubTool(result="different")
            reuses += id(fresh) == freed_address
            collisions += content_hash({"tool": fresh}) == freed_hash
            collisions += content_hash({"tools": [fresh]}) == freed_list_hash
            del fresh
    finally:
        gc.unfreeze()

    # Assert
    assert reuses > 0, "no address was reused; the regression loop tested nothing"
    assert collisions == 0


def test_freed_provider_hash_never_reappears_for_a_new_provider_at_its_address() -> None:
    # Arrange
    iterations = 250
    reuses = 0
    collisions = 0

    # Act
    gc.freeze()
    try:
        for _ in range(iterations):
            freed = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1")
            freed_address = id(freed)
            freed_hash = content_hash({"llm": freed})
            del freed
            gc.collect()
            fresh = OpenAICompatibleProvider(model="m-b", base_url="https://b.example/v1")
            reuses += id(fresh) == freed_address
            collisions += content_hash({"llm": fresh}) == freed_hash
            del fresh
    finally:
        gc.unfreeze()

    # Assert
    assert reuses > 0, "no address was reused; the regression loop tested nothing"
    assert collisions == 0


async def test_replay_never_serves_a_tool_built_after_the_recorded_one_was_freed() -> None:
    # Arrange
    iterations = 200
    served = 0
    reuses = 0

    # Act
    gc.freeze()
    try:
        for _ in range(iterations):
            was_served, was_reused = await _record_free_and_replay_tool()
            served += was_served
            reuses += was_reused
    finally:
        gc.unfreeze()

    # Assert
    assert reuses > 0, "no address was reused; the regression loop tested nothing"
    assert served == 0


async def _record_free_and_replay_tool() -> tuple[bool, bool]:
    """Record a ``ToolInvocation`` with tool A, free it, replay with a new tool B.

    Only the history and data store survive. The collection frees the recorded
    tapestry's cycles while this frame still holds A, and A is then released by
    reference count as the last object freed, so B usually lands at A's address.

    Returns:
        ``(served, reused)``: whether replay served A's recorded result, and
        whether B was allocated at A's freed address.
    """
    history, data_store = InMemoryHistory(), InMemoryDataStore()
    call = ToolCall(tool_name="stub_tool", arguments={"input": "x"}, call_id="c1")
    recorded_tool = StubTool(result="recorded")
    recorded_address = id(recorded_tool)
    with Tapestry(history=history, data_store=data_store) as recorded:
        ToolInvocation(tool=recorded_tool, call=call, _config=KnotConfig(id="invoke"))
    run = await recorded.run(RunRequest())
    del recorded
    gc.collect()
    del recorded_tool

    fresh_tool = StubTool(result="different")
    reused = id(fresh_tool) == recorded_address
    with Tapestry(history=history, data_store=data_store) as replaying:
        ToolInvocation(tool=fresh_tool, call=call, _config=KnotConfig(id="invoke"))
    session = await ReplaySession.from_history(history=history, run_id=run.run_id)
    try:
        await replaying.run(RunRequest(), replay=session)
    except ReplayMismatchError:
        return False, reused
    return True, reused
