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
                   ──► PromotionGate ──► next ModelEvaluator  (more models)
                                    ──► _RegistryReport       (queue exhausted)

Run with:
    uv run python examples/domain_formats/ml_evaluation_loop.py
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import statistics
from dataclasses import dataclass, replace
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry, get_current_store

REGISTRY_COMPLETE_ID = "registry_complete"

LATENCY_SLA_MS = 100.0
MEMORY_SLA_MB = 512.0
ACCURACY_THRESHOLD = 0.82


# ----------------------------------------------------------------- data models


@dataclass(frozen=True)
class ModelArtifact:
    model_id: str
    framework: str
    task: str
    tensors: dict  # layer_name -> {dtype, shape, data}
    metadata: dict


@dataclass(frozen=True)
class InferenceBatch:
    model_id: str
    batch_id: int
    predictions: tuple[float, ...]
    latency_ms: float
    throughput_samples_per_sec: float


@dataclass(frozen=True)
class LayerProfile:
    model_id: str
    total_params: int
    layer_count: int
    memory_mb: float
    compute_ops_per_sample: int


@dataclass(frozen=True)
class ModelMetrics:
    model_id: str
    accuracy: float
    f1: float
    latency_p50_ms: float
    latency_p99_ms: float
    memory_mb: float
    passes_latency_sla: bool
    passes_memory_sla: bool


@dataclass(frozen=True)
class PromotionDecision:
    model_id: str
    promoted: bool
    reason: str
    metrics: ModelMetrics


@dataclass(frozen=True)
class EvaluationQueue:
    models: tuple[ModelArtifact, ...]
    model_idx: int = 0
    decisions: tuple[PromotionDecision, ...] = ()

    @property
    def done(self) -> bool:
        return self.model_idx >= len(self.models)

    @property
    def current_model(self) -> ModelArtifact:
        return self.models[self.model_idx]

    def evolve(self, **changes) -> EvaluationQueue:
        return replace(self, **changes)


@dataclass(frozen=True)
class EvaluationReport:
    n_models: int
    promoted: list[str]
    rejected: list[str]
    decisions: tuple[PromotionDecision, ...]


# ----------------------------------------------------------------- synthetic data


def _rng(model_id: str, extra: str = "") -> random.Random:
    key = f"{model_id}|{extra}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _synthetic_model(model_id: str, framework: str, task: str) -> ModelArtifact:
    """Build a realistic-looking safetensors artifact for a given model."""
    rng = _rng(model_id, "arch")

    tensors: dict = {}

    if framework == "transformer":
        n_layers = rng.choice([6, 12, 24])
        hidden = rng.choice([256, 512, 768])
        vocab = rng.choice([8000, 16000, 32000])

        tensors["embedding.weight"] = {
            "dtype": "float32",
            "shape": [vocab, hidden],
            "data": [rng.gauss(0, 0.02) for _ in range(min(vocab * hidden, 256))],
        }
        for i in range(n_layers):
            tensors[f"layer.{i}.attention.q_proj.weight"] = {
                "dtype": "float16",
                "shape": [hidden, hidden],
                "data": [],
            }
            tensors[f"layer.{i}.attention.k_proj.weight"] = {
                "dtype": "float16",
                "shape": [hidden, hidden],
                "data": [],
            }
            tensors[f"layer.{i}.attention.v_proj.weight"] = {
                "dtype": "float16",
                "shape": [hidden, hidden],
                "data": [],
            }
            ffn_dim = hidden * 4
            tensors[f"layer.{i}.ffn.fc1.weight"] = {
                "dtype": "float16",
                "shape": [hidden, ffn_dim],
                "data": [],
            }
            tensors[f"layer.{i}.ffn.fc2.weight"] = {
                "dtype": "float16",
                "shape": [ffn_dim, hidden],
                "data": [],
            }
        tensors["classifier.weight"] = {
            "dtype": "float32",
            "shape": [hidden, rng.choice([2, 5, 10])],
            "data": [],
        }

    elif framework == "cnn":
        channels = [3, 64, 128, 256, 512]
        kernel = 3
        for i in range(len(channels) - 1):
            tensors[f"conv{i + 1}.weight"] = {
                "dtype": "float32",
                "shape": [channels[i + 1], channels[i], kernel, kernel],
                "data": [],
            }
            tensors[f"conv{i + 1}.bias"] = {
                "dtype": "float32",
                "shape": [channels[i + 1]],
                "data": [],
            }
            tensors[f"bn{i + 1}.weight"] = {
                "dtype": "float32",
                "shape": [channels[i + 1]],
                "data": [],
            }
        fc_in = channels[-1] * rng.choice([4, 7, 14])
        n_classes = rng.choice([10, 100, 1000])
        tensors["fc.weight"] = {
            "dtype": "float32",
            "shape": [fc_in, n_classes],
            "data": [],
        }

    else:  # rnn
        input_size = rng.choice([64, 128, 256])
        hidden_size = rng.choice([128, 256, 512])
        n_layers = rng.choice([1, 2, 3])
        for i in range(n_layers):
            in_size = input_size if i == 0 else hidden_size
            tensors[f"rnn.weight_ih_l{i}"] = {
                "dtype": "float32",
                "shape": [4 * hidden_size, in_size],
                "data": [],
            }
            tensors[f"rnn.weight_hh_l{i}"] = {
                "dtype": "float32",
                "shape": [4 * hidden_size, hidden_size],
                "data": [],
            }
        tensors["output.weight"] = {
            "dtype": "float32",
            "shape": [hidden_size, rng.choice([1, 2, 5])],
            "data": [],
        }

    metadata = {
        "model_id": model_id,
        "framework": framework,
        "task": task,
        "format_version": "1.0",
        "created_by": "pirn-registry",
    }
    return ModelArtifact(
        model_id=model_id,
        framework=framework,
        task=task,
        tensors=tensors,
        metadata=metadata,
    )


# ----------------------------------------------------------------- model catalogue


MODEL_CATALOGUE: tuple[ModelArtifact, ...] = tuple(
    _synthetic_model(model_id, framework, task)
    for model_id, framework, task in [
        ("bert-base-clf", "transformer", "classification"),
        ("resnet50-imgcls", "cnn", "classification"),
        ("lstm-regressor", "rnn", "regression"),
        ("gpt2-small-clf", "transformer", "classification"),
        ("convnet-tiny", "cnn", "regression"),
    ]
)


# ----------------------------------------------------------------- knots


def _evaluator_id(queue: EvaluationQueue) -> str:
    model_id = queue.current_model.model_id
    return f"eval__{model_id.replace('-', '_')}__{queue.model_idx}"


class ModelEvaluator(Knot):
    """Dynamic dispatcher — loads the current model and registers evaluation sub-graph."""

    async def process(self, queue: EvaluationQueue, **_) -> EvaluationQueue:  # type: ignore[override]
        store = get_current_store()
        if store is None:
            return queue

        model = queue.current_model
        prefix = self.knot_id

        batch_knot = BatchInference(
            artifact=model,
            _config=KnotConfig(id=f"{prefix}__batch", validate_io=False),
        )
        store.register(batch_knot)

        profiler_knot = LayerProfiler(
            artifact=model,
            _config=KnotConfig(id=f"{prefix}__profile", validate_io=False),
        )
        store.register(profiler_knot)

        agg = Aggregator(
            combine=lambda **kw: list(kw.values()),
            batches=batch_knot,
            profile=profiler_knot,
            _config=KnotConfig(id=f"{prefix}__agg", validate_io=False),
        )
        store.register(agg)

        metrics_knot = MetricsAggregator(
            combined=agg,
            _config=KnotConfig(id=f"{prefix}__metrics", validate_io=False),
        )
        store.register(metrics_knot)

        gate = PromotionGate(
            metrics=metrics_knot,
            queue=self,
            _config=KnotConfig(id=f"{prefix}__gate", validate_io=False),
        )
        store.register(gate)

        return queue


class BatchInference(Knot):
    """Run 3 synthetic inference batches against the model artifact."""

    async def process(self, artifact: ModelArtifact, **_) -> list[InferenceBatch]:  # type: ignore[override]
        rng = _rng(artifact.model_id, "inference")
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


class LayerProfiler(Knot):
    """Analyse tensor shapes to count params, estimate memory and FLOPs."""

    async def process(self, artifact: ModelArtifact, **_) -> LayerProfile:  # type: ignore[override]
        total_params = 0
        layer_count = len(artifact.tensors)
        compute_ops = 0

        for _name, tensor in artifact.tensors.items():
            shape = tensor["shape"]
            n_elements = math.prod(shape) if shape else 1
            total_params += n_elements
            # Estimate FLOPs: 2 multiplications per parameter for matmul-like ops
            if len(shape) >= 2:
                compute_ops += 2 * n_elements

        dtype_bytes = {"float32": 4, "float16": 2, "bfloat16": 2, "int8": 1}
        # Use float32 as fallback; sample from first tensor's dtype
        sample_dtype = "float32"
        if artifact.tensors:
            sample_dtype = next(iter(artifact.tensors.values())).get("dtype", "float32")
        bytes_per_param = dtype_bytes.get(sample_dtype, 4)
        memory_mb = (total_params * bytes_per_param) / (1024 * 1024)

        return LayerProfile(
            model_id=artifact.model_id,
            total_params=total_params,
            layer_count=layer_count,
            memory_mb=memory_mb,
            compute_ops_per_sample=compute_ops,
        )


class MetricsAggregator(Knot):
    """Collect BatchInference + LayerProfiler outputs and compute ModelMetrics."""

    async def process(self, combined: list, **_) -> ModelMetrics:  # type: ignore[override]
        batches: list[InferenceBatch] = []
        profile: LayerProfile | None = None

        for item in combined:
            if isinstance(item, list):
                batches = item
            elif isinstance(item, LayerProfile):
                profile = item

        if not batches or profile is None:
            raise ValueError("MetricsAggregator requires both batches and a profile")

        model_id = batches[0].model_id
        all_preds = [p for b in batches for p in b.predictions]
        pred_variance = statistics.variance(all_preds) if len(all_preds) > 1 else 0.0
        # Accuracy proxy: low variance around 0.5 suggests confident binary predictions
        accuracy = max(0.0, min(1.0, 1.0 - (pred_variance * 4.0)))

        # F1 proxy: accuracy ± small random perturbation seeded from model_id
        rng = _rng(model_id, "f1")
        f1 = max(0.0, min(1.0, accuracy + rng.uniform(-0.05, 0.05)))

        latencies = [b.latency_ms for b in batches]
        latencies_sorted = sorted(latencies)
        p50 = statistics.median(latencies_sorted)
        p99_idx = max(0, math.ceil(0.99 * len(latencies_sorted)) - 1)
        p99 = latencies_sorted[p99_idx]

        return ModelMetrics(
            model_id=model_id,
            accuracy=accuracy,
            f1=f1,
            latency_p50_ms=p50,
            latency_p99_ms=p99,
            memory_mb=profile.memory_mb,
            passes_latency_sla=p99 < LATENCY_SLA_MS,
            passes_memory_sla=profile.memory_mb < MEMORY_SLA_MB,
        )


class PromotionGate(Knot):
    """Decide promote/reject; register next ModelEvaluator or _RegistryReport."""

    async def process(  # type: ignore[override]
        self, metrics: ModelMetrics, queue: EvaluationQueue, **_
    ) -> PromotionDecision:
        reasons: list[str] = []
        if metrics.accuracy < ACCURACY_THRESHOLD:
            reasons.append(f"accuracy {metrics.accuracy:.3f} < {ACCURACY_THRESHOLD}")
        if not metrics.passes_latency_sla:
            reasons.append(f"p99 latency {metrics.latency_p99_ms:.1f}ms >= {LATENCY_SLA_MS}ms SLA")
        if not metrics.passes_memory_sla:
            reasons.append(f"memory {metrics.memory_mb:.1f}MB >= {MEMORY_SLA_MB}MB SLA")

        promoted = len(reasons) == 0
        reason = "all thresholds met" if promoted else "; ".join(reasons)

        decision = PromotionDecision(
            model_id=metrics.model_id,
            promoted=promoted,
            reason=reason,
            metrics=metrics,
        )

        new_decisions = (*queue.decisions, decision)
        new_queue = queue.evolve(
            model_idx=queue.model_idx + 1,
            decisions=new_decisions,
        )

        store = get_current_store()
        if store is None:
            return decision

        if not new_queue.done:
            next_evaluator = ModelEvaluator(
                queue=new_queue,
                _config=KnotConfig(id=_evaluator_id(new_queue), validate_io=False),
            )
            store.register(next_evaluator)
        else:
            store.register(
                _RegistryReport(
                    queue=new_queue,
                    _config=KnotConfig(id=REGISTRY_COMPLETE_ID, validate_io=False),
                )
            )

        return decision


class _RegistryReport(Knot):
    """Terminal knot — surfaces the final EvaluationReport."""

    async def process(self, queue: EvaluationQueue, **_) -> EvaluationReport:  # type: ignore[override]
        promoted = [d.model_id for d in queue.decisions if d.promoted]
        rejected = [d.model_id for d in queue.decisions if not d.promoted]
        return EvaluationReport(
            n_models=len(queue.decisions),
            promoted=promoted,
            rejected=rejected,
            decisions=queue.decisions,
        )


# ----------------------------------------------------------------- tapestry


def build_tapestry(catalogue: tuple[ModelArtifact, ...] | None = None, history=None) -> Tapestry:
    models = catalogue or MODEL_CATALOGUE
    queue = EvaluationQueue(models=models)
    t = Tapestry(history=history)
    first_evaluator = ModelEvaluator(
        queue=queue,
        _config=KnotConfig(id=_evaluator_id(queue), validate_io=False),
    )
    t.store.register(first_evaluator)
    return t


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    print("\n── ML Model Evaluation Loop ──\n")
    print(f"Registry: {len(MODEL_CATALOGUE)} candidate models\n")

    result = await t.run(extensible=True)

    if not result.succeeded:
        exc = result.exceptions[0] if result.exceptions else None
        print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:120] if exc else ''}")
        return

    report: EvaluationReport = result.outputs[REGISTRY_COMPLETE_ID]

    col_w = [22, 13, 16, 6, 12, 12, 10, 10]
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
        model = next(a for a in MODEL_CATALOGUE if a.model_id == decision.model_id)
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


if __name__ == "__main__":
    asyncio.run(main())
