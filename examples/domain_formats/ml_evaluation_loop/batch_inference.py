"""``BatchInference`` — runs synthetic inference batches against a model.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.ml_evaluation_loop.inference_batch import InferenceBatch
from examples.domain_formats.ml_evaluation_loop.model_artifact import ModelArtifact
from examples.domain_formats.ml_evaluation_loop.seeded_rng import SeededRng


class BatchInference(Knot):
    """Run 3 synthetic inference batches against the model artifact."""

    async def process(self, artifact: ModelArtifact, **_: Any) -> list[InferenceBatch]:
        rng = SeededRng.for_model(artifact.model_id, "inference")
        batches: list[InferenceBatch] = []
        for batch_id in range(3):
            batch_size = rng.choice([16, 32, 64])
            predictions = tuple(rng.gauss(0.5, 0.15) for _ in range(batch_size))
            latency_ms = rng.uniform(20.0, 150.0)
            throughput = (batch_size / latency_ms) * 1000.0
            batches.append(
                InferenceBatch(
                    model_id=artifact.model_id,
                    batch_id=batch_id,
                    predictions=predictions,
                    latency_ms=latency_ms,
                    throughput_samples_per_sec=throughput,
                )
            )
        return batches
