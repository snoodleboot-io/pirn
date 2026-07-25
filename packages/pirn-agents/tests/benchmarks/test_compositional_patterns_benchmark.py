"""Compositional-pattern micro-benchmarks for S8 (PIR-245).

``@pytest.mark.benchmark``; records the LLM round-trips each small compositional
pattern issues under the stub provider so regressions in call count are visible.
"""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.prompt_chaining.prompt_chain_pipeline import PromptChainPipeline
from pirn_agents.specializations.self_ask.self_ask_pipeline import SelfAskPipeline
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubLLMProvider


@pytest.mark.benchmark
async def test_self_ask_round_trips(benchmark_recorder: BenchmarkRecorder) -> None:
    # 1 decompose + 2 sub-answers + 1 compose = 4 round-trips for 2 sub-questions.
    llm = StubLLMProvider(["- a\n- b", "ans-a", "ans-b", "final"])
    with Tapestry() as t:
        SelfAskPipeline(task="q", llm=llm, _config=KnotConfig(id="sa"))
    run = await t.run(RunRequest())
    assert run.succeeded
    benchmark_recorder.record("SelfAskRoundTrips", round_trips=len(llm.calls))
    assert len(llm.calls) == 4


@pytest.mark.benchmark
async def test_prompt_chain_round_trips(benchmark_recorder: BenchmarkRecorder) -> None:
    llm = StubLLMProvider(["o1", "o2", "o3"])
    with Tapestry() as t:
        PromptChainPipeline(
            task="seed", llm=llm, steps=("a", "b", "c"), _config=KnotConfig(id="pc")
        )
    run = await t.run(RunRequest())
    assert run.succeeded
    benchmark_recorder.record("PromptChainRoundTrips", round_trips=len(llm.calls))
    # One round-trip per link.
    assert len(llm.calls) == 3
    report = benchmark_recorder.report()
    assert report.metric("PromptChainRoundTrips", "round_trips") == 3
