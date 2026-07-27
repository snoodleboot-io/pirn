"""End-to-end tests that built-in prompts honour the documented resolution order.

Covers both halves of the WS6-S1 contract:

* a loaded prompt pack retunes a shipped prompt with no code change;
* a subclass that overrides a public, documented ``ClassVar[str]`` still wins
  over that pack, so the two documented extension points do not fight.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.planning.planner import Planner
from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.specializations.chain_of_thought.chain_of_thought import ChainOfThought
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


class TerseReflectionCheck(ReflectionCheck):
    """Subclass exercising the documented ``reflection_prompt`` override."""

    reflection_prompt = "Answer yes or no."


class TersePlanner(Planner):
    """Subclass exercising the documented ``planning_instruction`` override."""

    planning_instruction = "List the steps."


class _SharedCatalogCase(unittest.IsolatedAsyncioTestCase):
    """Base case that keeps the process-wide catalog out of other tests."""

    def setUp(self) -> None:
        PromptCatalog.reset_shared()

    def tearDown(self) -> None:
        PromptCatalog.reset_shared()

    @staticmethod
    def _load(name: str, body: str) -> None:
        PromptCatalog.shared().load_mapping({"templates": {name: body}})


class PackOverridesBuiltinTests(_SharedCatalogCase):
    """A loaded pack retunes a shipped prompt without touching Python."""

    async def test_pack_retunes_a_private_prompt(self) -> None:
        self._load(
            "specializations.chain_of_thought.chain_of_thought.system_prompt",
            "Reason aloud, in French.",
        )
        llm = StubLLMProvider(responses=["ok"])
        with Tapestry():
            cot = ChainOfThought(prompt="q", llm=llm, _config=KnotConfig(id="cot"))
        await cot.process(prompt="q", llm=llm)
        assert llm.calls[0][0]["content"] == "Reason aloud, in French."

    async def test_pack_retunes_a_public_prompt(self) -> None:
        self._load("control.reflection_check.reflection_prompt", "Iterate? yes/no.")
        llm = StubLLMProvider(responses=["no"])
        with Tapestry():
            upstream = _stub_response(_config=KnotConfig(id="r"))
            check = ReflectionCheck(response=upstream, llm=llm, _config=KnotConfig(id="c"))
        await check.process(response=AgentResponse(content="answer"), llm=llm)
        assert llm.calls[0][0]["content"] == "Iterate? yes/no."

    async def test_pack_variables_render_into_the_delivered_prompt(self) -> None:
        self._load(
            "planning.planner.planning_instruction",
            "Plan for {{ audience }}.",
        )
        llm = StubLLMProvider(responses=["1. go"])
        with Tapestry():
            upstream = _stub_context(_config=KnotConfig(id="ctx2"))
            planner = Planner(context=upstream, llm=llm, _config=KnotConfig(id="p2"))
        context = AgentContext(messages=(AgentMessage(role="user", content="go"),))
        await planner.process(context=context, llm=llm)
        # No variables are supplied at this site, so the slot stays literal
        # rather than raising mid-turn.
        assert llm.calls[0][0]["content"] == "Plan for {{ audience }}."


class SubclassOverrideWinsTests(_SharedCatalogCase):
    """A subclass override beats a loaded pack for the two public class vars."""

    async def test_reflection_check_subclass_beats_a_loaded_pack(self) -> None:
        self._load("control.reflection_check.reflection_prompt", "PACK TEXT")
        llm = StubLLMProvider(responses=["no"])
        with Tapestry():
            upstream = _stub_response(_config=KnotConfig(id="r3"))
            check = TerseReflectionCheck(response=upstream, llm=llm, _config=KnotConfig(id="c3"))
        await check.process(response=AgentResponse(content="answer"), llm=llm)
        assert llm.calls[0][0]["content"] == "Answer yes or no."

    async def test_planner_subclass_beats_a_loaded_pack(self) -> None:
        self._load("planning.planner.planning_instruction", "PACK TEXT")
        llm = StubLLMProvider(responses=["1. go"])
        with Tapestry():
            upstream = _stub_context(_config=KnotConfig(id="ctx4"))
            planner = TersePlanner(context=upstream, llm=llm, _config=KnotConfig(id="p4"))
        context = AgentContext(messages=(AgentMessage(role="user", content="go"),))
        await planner.process(context=context, llm=llm)
        assert llm.calls[0][0]["content"] == "List the steps."

    async def test_reflection_check_subclass_wins_with_no_pack_loaded(self) -> None:
        llm = StubLLMProvider(responses=["no"])
        with Tapestry():
            upstream = _stub_response(_config=KnotConfig(id="r5"))
            check = TerseReflectionCheck(response=upstream, llm=llm, _config=KnotConfig(id="c5"))
        await check.process(response=AgentResponse(content="answer"), llm=llm)
        assert llm.calls[0][0]["content"] == "Answer yes or no."

    def test_public_class_vars_still_read_as_the_builtin_text(self) -> None:
        # The documented attributes remain plain, readable strings.
        assert ReflectionCheck.reflection_prompt.startswith("You are an agent reflection assistant.")
        assert Planner.planning_instruction.startswith("You are a planning assistant.")


class BuiltinNameCoverageTests(unittest.TestCase):
    """Every converted site declares a distinct, module-derived binding name."""

    def test_converted_binding_names_are_unique_and_module_derived(self) -> None:
        from pirn_agents.specializations.chain_of_thought.step_back_prompting import (
            StepBackPrompting,
        )
        from pirn_agents.specializations.chain_of_thought.tree_of_thought import TreeOfThought
        from pirn_agents.specializations.plan_and_execute.plan_executor import PlanExecutor
        from pirn_agents.specializations.plan_and_execute.plan_revisor import PlanRevisor
        from pirn_agents.specializations.plan_and_execute.task_planner import TaskPlanner
        from pirn_agents.specializations.reflection.constitutional_filter import (
            ConstitutionalFilter,
        )
        from pirn_agents.specializations.reflection.outcome_simulator import OutcomeSimulator
        from pirn_agents.specializations.reflection.self_critique_revise import SelfCritiqueRevise

        bindings = [
            ReflectionCheck._reflection_prompt,
            Planner._planning_instruction,
            ChainOfThought._system_prompt,
            StepBackPrompting._step_back_system,
            StepBackPrompting._forward_system,
            TreeOfThought._expansion_system,
            TreeOfThought._scoring_system,
            PlanExecutor._step_system,
            PlanRevisor._revision_system,
            TaskPlanner._planning_system,
            ConstitutionalFilter._evaluation_system,
            OutcomeSimulator._simulation_system,
            SelfCritiqueRevise._generation_system,
            SelfCritiqueRevise._critique_system,
            SelfCritiqueRevise._revision_system,
        ]
        names = [b.name for b in bindings]
        assert len(names) == 15
        assert len(set(names)) == 15
        for binding in bindings:
            assert binding.namespace == PromptCatalog.builtin_namespace()
            assert binding.default, f"{binding.name} has an empty built-in default"
            assert "." in binding.name, f"{binding.name} is not module-derived"
