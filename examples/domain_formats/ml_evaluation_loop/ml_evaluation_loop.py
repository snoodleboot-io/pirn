"""Example: Iterative ML model evaluation as a dynamic DAG.

A model registry contains multiple candidate models stored as safetensors
artifacts.  An evaluation loop loads each model, runs synthetic inference
batches, profiles layer structure, computes metrics, and decides whether to
promote the model to production or reject it.

The whole registry sweep is ONE extensible run — the graph grows with each
model as knots register their successors directly.

Architecture (one iteration per model):

    ModelEvaluator ──► BatchInference, LayerProfiler  (concurrent)
                   ──► MetricsAggregator
                   ──► PromotionDecider ──► next ModelEvaluator  (more models)
                                       ──► _RegistryReport       (queue exhausted)

Run with:
    uv run python -m examples.domain_formats.ml_evaluation_loop
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.domain_formats.ml_evaluation_loop.evaluation_queue import EvaluationQueue
from examples.domain_formats.ml_evaluation_loop.evaluation_report import EvaluationReport
from examples.domain_formats.ml_evaluation_loop.model_artifact import ModelArtifact
from examples.domain_formats.ml_evaluation_loop.model_evaluator import ModelEvaluator
from examples.domain_formats.ml_evaluation_loop.registry_ids import RegistryIds


class MlEvaluationLoop:
    """Builds the candidate registry, sweeps it in one extensible run, prints the verdicts."""

    _model_catalogue: ClassVar[tuple[tuple[str, str, str], ...]] = (
        ("bert-base-clf", "transformer", "classification"),
        ("resnet50-imgcls", "cnn", "classification"),
        ("lstm-regressor", "rnn", "regression"),
        ("gpt2-small-clf", "transformer", "classification"),
        ("convnet-tiny", "cnn", "regression"),
    )
    _column_widths: ClassVar[tuple[int, ...]] = (22, 13, 16, 6, 12, 12, 10, 10)

    @classmethod
    def catalogue(cls) -> tuple[ModelArtifact, ...]:
        """Materialise every candidate named by ``_model_catalogue``."""
        return tuple(
            ModelArtifact.synthetic(model_id, framework, task)
            for model_id, framework, task in cls._model_catalogue
        )

    @classmethod
    def build_tapestry(
        cls,
        catalogue: tuple[ModelArtifact, ...] | None = None,
        history: SQLiteHistory | None = None,
    ) -> Tapestry:
        """Seed a tapestry with the first evaluator; the run grows the rest."""
        models = catalogue or cls.catalogue()
        queue = EvaluationQueue(models=models)
        t = Tapestry(history=history)
        first_evaluator = ModelEvaluator(
            queue=queue,
            _config=KnotConfig(id=queue.evaluator_id(), validate_io=False),
        )
        t.store.register(first_evaluator)
        return t

    @classmethod
    async def main(cls) -> None:
        """Evaluate every candidate model and print the promotion table."""
        catalogue = cls.catalogue()
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(catalogue=catalogue, history=history)

        print("\n── ML Model Evaluation Loop ──\n")
        print(f"Registry: {len(catalogue)} candidate models\n")

        result = await t.run(extensible=True)

        if not result.succeeded:
            exc = result.exceptions[0] if result.exceptions else None
            print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:120] if exc else ''}")
            return

        report: EvaluationReport = result.outputs[RegistryIds.complete]

        col_w = cls._column_widths
        header = (
            f"{'Model':<{col_w[0]}}"
            f"{'Framework':<{col_w[1]}}"
            f"{'Task':<{col_w[2]}}"
            f"{'Acc':>{col_w[3]}}"
            f"{'p50 ms':>{col_w[4]}}"
            f"{'p99 ms':>{col_w[5]}}"
            f"{'Mem MB':>{col_w[6]}}"
            f"{'Result':>{col_w[7]}}"
        )
        separator = "-" * sum(col_w)

        print(header)
        print(separator)

        for decision in report.decisions:
            m = decision.metrics
            model = next(a for a in catalogue if a.model_id == decision.model_id)
            status = "PROMOTE" if decision.promoted else "REJECT"
            print(
                f"{decision.model_id:<{col_w[0]}}"
                f"{model.framework:<{col_w[1]}}"
                f"{model.task:<{col_w[2]}}"
                f"{m.accuracy:>{col_w[3]}.3f}"
                f"{m.latency_p50_ms:>{col_w[4]}.1f}"
                f"{m.latency_p99_ms:>{col_w[5]}.1f}"
                f"{m.memory_mb:>{col_w[6]}.1f}"
                f"{status:>{col_w[7]}}"
            )

        print(separator)
        print(
            f"\nSummary: {report.n_models} evaluated · "
            f"{len(report.promoted)} promoted · {len(report.rejected)} rejected\n"
        )

        if report.promoted:
            print(f"Promoted to production : {', '.join(report.promoted)}")
        if report.rejected:
            print(f"Rejected               : {', '.join(report.rejected)}")

        for decision in report.decisions:
            if not decision.promoted:
                print(f"  {decision.model_id}: {decision.reason}")

        print()
