"""End-to-end fixture test: a ReActLoop solves a task with >=3 base tools (PIR-239).

A stub-LLM-driven :class:`ReActLoop` is registered with a :class:`Toolset`
assembled from the curated bundle factories, then scripted to invoke three
distinct base tools — ``calculator``, ``html_to_text``, and ``retriever`` — before
emitting a final answer. This proves the base tools compose with the agent loop
via a Toolset, using only stub doubles (no network, no vendor SDK).
"""

from __future__ import annotations

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.tools.bundles import calculator_toolset, retrieval_toolset, web_toolset
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from tests.conftest import StubLLMProvider, StubMemoryStore


async def test_react_loop_solves_task_with_three_base_tools() -> None:
    store = StubMemoryStore()
    await store.store("g", {"text": "Hello from the knowledge base."})

    toolset = calculator_toolset() + web_toolset() + retrieval_toolset(store=store)
    # The bundle assembly must expose the three tools the agent will call.
    assert {"calculator", "html_to_text", "retriever"} <= {t.name for t in toolset}

    llm = StubLLMProvider(
        [
            "Thought: compute first.\nAction: calculator\nAction Input: 21 * 2",
            "Thought: clean the html.\nAction: html_to_text\nAction Input: <b>Hi</b> there",
            "Thought: look it up.\nAction: retriever\nAction Input: greeting",
            "Final Answer: done",
        ]
    )

    with Tapestry() as tapestry:
        ReActLoop(
            messages=(AgentMessage(role="user", content="Solve the task."),),
            llm=llm,
            tools=tuple(toolset),
            max_iterations=6,
            _config=KnotConfig(id="loop"),
        )
    run = await tapestry.run(RunRequest())

    assert run.succeeded
    response = run.outputs["loop"]
    assert isinstance(response, AgentResponse)
    assert response.content == "done"

    # The retriever actually queried the store.
    assert store.searched == ["greeting"]
    # The final LLM prompt carries the observations from all three tool calls,
    # proving each base tool executed and fed its result back into the loop.
    final_prompt = llm.calls[-1][-1]["content"]
    assert "42" in final_prompt
    assert "Hi there" in final_prompt
    assert "Hello from the knowledge base." in final_prompt
