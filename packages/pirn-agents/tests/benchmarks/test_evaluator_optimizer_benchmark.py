"""Evaluator-Optimizer convergence micro-benchmark (PIR-217).

``@pytest.mark.benchmark``; measures how many generate/judge rounds the accept
loop needs to clear the threshold under the stub provider.
"""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_pipeline import (
    EvaluatorOptimizerPipeline,
)
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubLLMProvider


@pytest.mark.benchmark
async def test_evaluator_optimizer_convergence(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    # Scores climb 4 -> 6 -> 9, clearing the threshold on the third round.
    llm = StubLLMProvider(
        ["c1", "SCORE: 4\nweak", "c2", "SCORE: 6\nbetter", "c3", "SCORE: 9\ngood"]
    )
    with Tapestry() as t:
        EvaluatorOptimizerPipeline(
            task="fixture task",
            llm=llm,
            threshold=8.0,
            max_iterations=5,
            _config=KnotConfig(id="eo"),
        )
    run = await t.run(RunRequest())
    assert run.succeeded
    result = run.outputs["eo"]
    assert result.accepted is True

    benchmark_recorder.record(
        "EvaluatorOptimizerConvergence",
        iterations=result.iterations,
        final_score=result.score,
    )
    report = benchmark_recorder.report()
    assert report.metric("EvaluatorOptimizerConvergence", "iterations") == 3
