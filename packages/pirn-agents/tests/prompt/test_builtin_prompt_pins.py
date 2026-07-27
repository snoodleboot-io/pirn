"""Byte-identity pins for every built-in system prompt routed through the registry.

Each test drives the owning knot's ``process()`` with a stub provider and asserts
the exact ``{"role": "system"}`` content that reaches ``LLMProvider.chat``. The
expected strings are copied byte-for-byte from the pre-WS6 class-var literals, so
these pins fail the moment a registry-resolution change alters delivered text.

Written before the WS6-S1 conversion and green on the unconverted source; the
conversion must keep them green without edits.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.planning.plan import Plan
from pirn_agents.planning.planner import Planner
from pirn_agents.specializations.chain_of_thought.chain_of_thought import ChainOfThought
from pirn_agents.specializations.chain_of_thought.step_back_prompting import StepBackPrompting
from pirn_agents.specializations.chain_of_thought.tree_of_thought import TreeOfThought
from pirn_agents.specializations.plan_and_execute.plan_executor import PlanExecutor
from pirn_agents.specializations.plan_and_execute.plan_revisor import PlanRevisor
from pirn_agents.specializations.plan_and_execute.task_planner import TaskPlanner
from pirn_agents.specializations.reflection.constitutional_filter import ConstitutionalFilter
from pirn_agents.specializations.reflection.outcome_simulator import OutcomeSimulator
from pirn_agents.specializations.reflection.self_critique_revise import SelfCritiqueRevise
from pirn_agents.types.messaging.agent_context import AgentContext
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.conftest import StubLLMProvider


@knot
async def _stub_response() -> AgentResponse:
    return AgentResponse(content="x")


@knot
async def _stub_context() -> AgentContext:
    return AgentContext(messages=())


@knot
async def _stub_plan() -> Plan:
    return Plan(steps=("a",))


class ControlPromptPins(unittest.IsolatedAsyncioTestCase):
    """`control/` prompt text is delivered byte-for-byte."""

    async def test_reflection_check_reflection_prompt(self) -> None:
        llm = StubLLMProvider(responses=["yes"])
        with Tapestry():
            upstream = _stub_response(_config=KnotConfig(id="r"))
            check = ReflectionCheck(response=upstream, llm=llm, _config=KnotConfig(id="c"))
        await check.process(response=AgentResponse(content="answer"), llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are an agent reflection assistant. Given the response "
            "below, decide whether the agent should iterate again to "
            "improve it. Answer 'yes' to iterate or 'no' to stop. Reply "
            "with the single word only."
        )


class PlanningPromptPins(unittest.IsolatedAsyncioTestCase):
    """`planning/` prompt text is delivered byte-for-byte."""

    async def test_planner_planning_instruction(self) -> None:
        llm = StubLLMProvider(responses=["1. do a thing"])
        with Tapestry():
            upstream = _stub_context(_config=KnotConfig(id="ctx"))
            planner = Planner(context=upstream, llm=llm, _config=KnotConfig(id="p"))
        context = AgentContext(messages=(AgentMessage(role="user", content="go"),))
        await planner.process(context=context, llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are a planning assistant. Given the conversation so far, "
            "produce a numbered list of concrete steps the agent should "
            "take next. One step per line. Lines starting with '#' are "
            "treated as rationale and may explain your reasoning."
        )


class ChainOfThoughtPromptPins(unittest.IsolatedAsyncioTestCase):
    """`specializations/chain_of_thought/` prompt text is delivered byte-for-byte."""

    async def test_chain_of_thought_system_prompt(self) -> None:
        llm = StubLLMProvider(responses=["reasoning"])
        with Tapestry():
            cot = ChainOfThought(prompt="q", llm=llm, _config=KnotConfig(id="cot"))
        await cot.process(prompt="q", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "Think step-by-step. Show your reasoning before stating your final answer."
        )

    async def test_step_back_prompting_both_systems(self) -> None:
        llm = StubLLMProvider(responses=["principles", "answer"])
        with Tapestry():
            sb = StepBackPrompting(prompt="q", llm=llm, _config=KnotConfig(id="sb"))
        await sb.process(prompt="q", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are an expert at identifying the underlying principles and "
            "concepts relevant to a question. Given the question below, first "
            "ask and answer a more abstract, high-level question whose answer "
            "would be useful context for answering the original question."
        )
        assert llm.calls[1][0]["content"] == (
            "You are a helpful assistant. Use the provided background principles "
            "to answer the original question accurately."
        )

    async def test_tree_of_thought_expansion_and_scoring_systems(self) -> None:
        llm = StubLLMProvider(responses=["thought", "5"])
        with Tapestry():
            tot = TreeOfThought(prompt="q", llm=llm, _config=KnotConfig(id="tot"))
        await tot.process(prompt="q", llm=llm, k_candidates=1, beam_width=1, depth=1)
        assert llm.calls[0][0]["content"] == (
            "You are a reasoning assistant. Generate the next reasoning step "
            "that continues the following thought chain."
        )
        assert llm.calls[1][0]["content"] == (
            "You are a reasoning evaluator. Rate the quality of the following "
            "reasoning step on a scale from 1 to 10. Reply with a single integer only."
        )


class PlanAndExecutePromptPins(unittest.IsolatedAsyncioTestCase):
    """`specializations/plan_and_execute/` prompt text is delivered byte-for-byte."""

    async def test_plan_executor_step_system(self) -> None:
        llm = StubLLMProvider(responses=["done"])
        with Tapestry():
            upstream = _stub_plan(_config=KnotConfig(id="pl"))
            executor = PlanExecutor(plan=upstream, llm=llm, _config=KnotConfig(id="ex"))
        await executor.process(plan=Plan(steps=("a",)), llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are a task executor. Complete the given step accurately and concisely. "
            "Use the previous step results as context where relevant."
        )

    async def test_plan_revisor_revision_system(self) -> None:
        llm = StubLLMProvider(responses=["1. recover"])
        with Tapestry():
            revisor = PlanRevisor(
                original_plan=Plan(steps=()),
                completed_results="",
                failure_reason="",
                llm=llm,
                _config=KnotConfig(id="rev"),
            )
        await revisor.process(
            original_plan=Plan(steps=("a",)),
            completed_results="",
            failure_reason="boom",
            llm=llm,
        )
        assert llm.calls[0][0]["content"] == (
            "You are an expert planner. A task plan has partially failed. "
            "Given the original plan, the completed results so far, and the "
            "failure reason, produce a revised numbered list of remaining steps "
            "to recover and complete the goal. Use the format:\n"
            "1. <first remaining step>\n2. <second remaining step>\n..."
        )

    async def test_task_planner_planning_system(self) -> None:
        llm = StubLLMProvider(responses=["1. step one"])
        with Tapestry():
            tp = TaskPlanner(goal="g", llm=llm, _config=KnotConfig(id="tp"))
        await tp.process(goal="g", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are an expert planner. Decompose the goal below into a numbered "
            "list of clear, actionable steps. Use the format:\n"
            "1. <first step>\n2. <second step>\n..."
        )


class ReflectionPromptPins(unittest.IsolatedAsyncioTestCase):
    """`specializations/reflection/` prompt text is delivered byte-for-byte."""

    async def test_constitutional_filter_evaluation_system(self) -> None:
        llm = StubLLMProvider(responses=["COMPLIANT"])
        with Tapestry():
            upstream = _stub_response(_config=KnotConfig(id="r2"))
            cf = ConstitutionalFilter(
                response=upstream,
                principles=("Be helpful.",),
                llm=llm,
                _config=KnotConfig(id="cf"),
            )
        await cf.process(
            response=AgentResponse(content="answer"),
            principles=("Be helpful.",),
            llm=llm,
            max_revisions=1,
        )
        assert llm.calls[0][0]["content"] == (
            "You are a constitutional AI reviewer. Evaluate the response against "
            "the principles listed below. If the response violates any principle, "
            "describe the violation and provide a revised response that is compliant. "
            "If the response is fully compliant, reply with exactly: COMPLIANT"
        )

    async def test_outcome_simulator_simulation_system(self) -> None:
        llm = StubLLMProvider(responses=["Best case:\nfine"])
        with Tapestry():
            sim = OutcomeSimulator(action="a", llm=llm, _config=KnotConfig(id="sim"))
        await sim.process(action="a", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are a strategic advisor. Given the proposed action below, "
            "simulate three plausible outcomes. Use exactly these section headers "
            "on their own lines:\nBest case:\nNeutral case:\nWorst case:\n"
            "Provide a concise description under each header."
        )

    async def test_self_critique_revise_all_three_systems(self) -> None:
        llm = StubLLMProvider(responses=["initial", "critique", "revised"])
        with Tapestry():
            scr = SelfCritiqueRevise(prompt="q", llm=llm, _config=KnotConfig(id="scr"))
        await scr.process(prompt="q", llm=llm)
        assert llm.calls[0][0]["content"] == (
            "You are a helpful assistant. Answer the question as accurately "
            "and completely as you can."
        )
        assert llm.calls[1][0]["content"] == (
            "You are a critical reviewer. Identify the main weaknesses, errors, "
            "or gaps in the following answer. Be concise and specific."
        )
        assert llm.calls[2][0]["content"] == (
            "You are a helpful assistant. Given the original question, the initial "
            "answer, and a critique of that answer, produce an improved final answer "
            "that addresses the critique."
        )
