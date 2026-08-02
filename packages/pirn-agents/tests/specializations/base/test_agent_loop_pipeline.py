"""Contract tests for :class:`AgentLoopPipeline`."""

from __future__ import annotations

import unittest

from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline


class TestAgentLoopPipelineIdentity(unittest.TestCase):
    """The seam exists so a loop pipeline is both things by construction."""

    def test_is_a_loop_sub_tapestry(self) -> None:
        assert issubclass(AgentLoopPipeline, LoopSubTapestry)

    def test_is_an_agent_pipeline(self) -> None:
        """Family membership — `test_agent_pipeline_base` requires it of every
        SubTapestry under specializations/, private helpers included."""
        assert issubclass(AgentLoopPipeline, AgentPipeline)
        assert issubclass(AgentLoopPipeline, SubTapestry)

    def test_process_resolves_to_the_loop_driver(self) -> None:
        """MRO order is load-bearing: AgentPipeline.process is abstract, so if it
        won the lookup every loop would raise NotImplementedError."""
        assert AgentLoopPipeline.process is LoopSubTapestry.process
        assert AgentLoopPipeline.process is not AgentPipeline.process

    def test_mro_puts_the_loop_first(self) -> None:
        mro = AgentLoopPipeline.__mro__
        assert mro.index(LoopSubTapestry) < mro.index(AgentPipeline)
