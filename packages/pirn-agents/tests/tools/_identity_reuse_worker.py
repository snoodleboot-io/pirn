"""Subprocess worker for the pirn-agents address-reuse loops (PIR-852).

Run as ``python _identity_reuse_worker.py <scenario> <iterations>``. It prints
``{"iterations": n, "reuses": n, "collisions": n}``. ``reuses`` counts rebuilt
objects that landed at the freed object's address (the precondition that makes
a loop meaningful). ``collisions`` counts how often such an object still matched
the freed one: an equal hash, or replay serving the recording.

The loops run in a fresh interpreter because, inside a large coverage-traced
test process, CI saw no address reuse at all. The parent strips coverage's
subprocess hooks before starting this worker. Within the worker, reuse is made
deliberate rather than lucky (measured on Python 3.11 to 3.14):

* the freed object is emptied and dropped by reference count, so its block is
  the last one freed (:func:`release_by_refcount`);
* replacements are allocated with a bare ``__new__`` and initialised only once
  one has claimed the address (:func:`claim_freed_address`). An ``__init__``
  allocates same-size helper objects that would otherwise take the block.
"""

from __future__ import annotations

import asyncio
import gc
import json
import sys
from collections.abc import Callable
from typing import Any

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


def release_by_refcount(value: Any) -> None:
    """Empty ``value``'s instance dict so dropping it frees it immediately.

    Tools and providers keep bound methods and back-references on themselves,
    so a plain ``del`` leaves them to the cycle collector, which frees other
    same-size garbage after them. With the attributes cleared first, the
    value's own block is the last one freed. Its hash and token were already
    taken, so emptying it changes nothing under test.
    """
    vars(value).clear()


def claim_freed_address(new_args: tuple[type], address: int, slots: list[Any]) -> Any:
    """Allocate bare ``new_args[0]`` instances into ``slots`` until one lands at ``address``.

    ``slots`` must be allocated before the victim is freed, and the loop avoids
    creating objects of its own (small-int counter, no iterator). ``new_args`` is
    the ``(cls,)`` tuple, also built before the free: ``cls.__new__(cls)`` would
    allocate a fresh argument tuple on every call. On Python 3.11
    a fresh list or range iterator shares the victim's size class and takes the
    block first.

    Returns:
        The uninitialised instance at ``address``, or the first one allocated
        if none landed there. The caller initialises it.
    """
    index = 0
    while index < len(slots):
        slots[index] = new_args[0].__new__(*new_args)
        if id(slots[index]) == address:
            return slots[index]
        index += 1
    return slots[0]


def stub_tool_hash_once() -> tuple[bool, bool]:
    """Free a ``StubTool``, build another at its address; compare bare and list hashes."""
    slots: list[Any] = [None] * 1024
    new_args = (StubTool,)
    freed = StubTool(result="recorded")
    freed_address = id(freed)
    freed_hash = content_hash({"tool": freed})
    freed_list_hash = content_hash({"tools": [freed]})
    gc.collect()
    release_by_refcount(freed)
    del freed
    fresh = claim_freed_address(new_args, freed_address, slots)
    fresh.__init__(result="different")
    collided = (
        content_hash({"tool": fresh}) == freed_hash
        or content_hash({"tools": [fresh]}) == freed_list_hash
    )
    return id(fresh) == freed_address, collided


def provider_hash_once() -> tuple[bool, bool]:
    """Free an HTTP provider, build one for another model at its address; compare hashes."""
    slots: list[Any] = [None] * 1024
    new_args = (OpenAICompatibleProvider,)
    freed = OpenAICompatibleProvider(model="m-a", base_url="https://a.example/v1")
    freed_address = id(freed)
    freed_hash = content_hash({"llm": freed})
    gc.collect()
    release_by_refcount(freed)
    del freed
    fresh = claim_freed_address(new_args, freed_address, slots)
    fresh.__init__(model="m-b", base_url="https://b.example/v1")
    collided = content_hash({"llm": fresh}) == freed_hash
    return id(fresh) == freed_address, collided


async def tool_replay_once() -> tuple[bool, bool]:
    """Record a ``ToolInvocation`` with tool A, free it, replay with a new tool B.

    Only the history and data store survive. ``collided`` means replay served
    A's recorded result instead of refusing.
    """
    slots: list[Any] = [None] * 1024
    new_args = (StubTool,)
    history, data_store = InMemoryHistory(), InMemoryDataStore()
    call = ToolCall(tool_name="stub_tool", arguments={"input": "x"}, call_id="c1")
    recorded_tool = StubTool(result="recorded")
    recorded_address = id(recorded_tool)
    with Tapestry(history=history, data_store=data_store) as recorded:
        ToolInvocation(tool=recorded_tool, call=call, _config=KnotConfig(id="invoke"))
    run_id = (await recorded.run(RunRequest())).run_id
    del recorded
    gc.collect()
    release_by_refcount(recorded_tool)
    del recorded_tool

    fresh_tool = claim_freed_address(new_args, recorded_address, slots)
    fresh_tool.__init__(result="different")
    reused = id(fresh_tool) == recorded_address
    with Tapestry(history=history, data_store=data_store) as replaying:
        ToolInvocation(tool=fresh_tool, call=call, _config=KnotConfig(id="invoke"))
    session = await ReplaySession.from_history(history=history, run_id=run_id)
    try:
        await replaying.run(RunRequest(), replay=session)
    except ReplayMismatchError:
        return reused, False
    return reused, True


def tally_sync(step: Callable[[], tuple[bool, bool]], iterations: int) -> dict[str, int]:
    """Run a synchronous loop body ``iterations`` times."""
    reuses = collisions = 0
    for _ in range(iterations):
        reused, collided = step()
        reuses += reused
        collisions += collided
    return {"iterations": iterations, "reuses": reuses, "collisions": collisions}


async def tally_replay(iterations: int) -> dict[str, int]:
    """Run the replay loop body ``iterations`` times."""
    reuses = collisions = 0
    for _ in range(iterations):
        reused, collided = await tool_replay_once()
        reuses += reused
        collisions += collided
    return {"iterations": iterations, "reuses": reuses, "collisions": collisions}


def main(scenario: str, iterations: int) -> dict[str, int]:
    """Dispatch ``scenario`` and return its tally."""
    if scenario == "tool_replay":
        return asyncio.run(tally_replay(iterations))
    steps: dict[str, Callable[[], tuple[bool, bool]]] = {
        "stub_tool_hash": stub_tool_hash_once,
        "provider_hash": provider_hash_once,
    }
    return tally_sync(steps[scenario], iterations)


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], int(sys.argv[2]))))
