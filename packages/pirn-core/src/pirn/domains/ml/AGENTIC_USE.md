# AGENTIC_USE — pirn.domains.ml

> This domain provides typed, async knots for the full ML lifecycle (data prep through deployment and lineage) — it does NOT include data-storage backends, streaming infrastructure, or the training framework libraries themselves (those are user-supplied).

---

## Mental model

The ML pipeline maps directly onto pirn's knot graph:

```
DatasetLoader → TrainTestSplit → [Scaler / Encoder / Imputer / EmbeddingExtractor]
    → Trainer / HyperparamSearch / EnsembleBuilder
    → Evaluator → MetricGate
    → ModelSerializer → ModelRegistrar
    → Predictor / ShadowDeployer
```

Each stage is a `Knot`. Wire them in a `Tapestry` context; pirn handles execution order, content-addressed lineage, and result routing. Swap any knot without touching adjacent knots.

**Artifact formats** are separate connector classes (`pirn/domains/connectors/file_formats/`) and plug into `ModelSerializer` (or are used standalone). Each format class receives or emits raw bytes and surfaces metadata alongside the artifact. Two formats — `JoblibFormat` and `PytorchFormat` — wrap pickle-based serialisation; both enforce an HMAC-SHA256 signing contract by default. `SafetensorsFormat`, `OnnxFormat`, `GgufFormat`, and `TfliteFormat` have no pickle path and need no signer.

**Provider interfaces** (`EmbeddingProvider`, `FeatureStoreProvider`, `ImageEncoderProvider`, `LineageStore`) define the external-system contracts. You supply the implementation; pirn defines what it calls.

---

## Install

```bash
# Core ML domain (numpy, pandas, scikit-learn).
pip install pirn[ml]

# Artifact format extras — add what you need:
pip install pirn[onnx]          # OnnxFormat — ONNX validation
pip install pirn[safetensors]   # SafetensorsFormat — Hugging Face safetensors
pip install pirn[joblib]        # JoblibFormat — scikit-learn / joblib persistence
pip install pirn[pytorch]       # PytorchFormat — PyTorch state dicts
pip install pirn[tensorflow]    # TfSavedModelFormat — TF SavedModel + TFLite fallback
pip install pirn[gguf]          # GgufFormat — llama.cpp quantised weights
pip install pirn[tflite]        # TfliteFormat — TFLite runtime (lighter than full TF)
```

---

## Source map

```
pirn/domains/ml/
├── __init__.py                     # empty public surface; lazy-import pattern
├── types/                          # shared value types
│   ├── ml_dataset.py               # MLDataset — feature DataFrame + optional label Series
│   ├── data_split.py               # DataSplit — train/test or train/val split pair
│   ├── trained_model.py            # TrainedModel — fitted estimator + metadata
│   └── eval_report.py              # EvalReport — metrics, confusion matrix, pass/fail flag
├── embedding_provider.py           # Interface: embed(texts, *, model) -> list[list[float]]
├── feature_store_provider.py       # Interface: get_features / write_features
├── image_encoder_provider.py       # Interface: encode(images, *, model) -> list[list[float]]
├── lineage_store.py                # Interface: log_event / fetch_lineage
├── data_prep/
│   ├── dataset_loader.py           # Load from FeatureStoreProvider or MLDataset
│   ├── train_test_split.py         # Split with optional stratification
│   ├── sampler.py                  # Over/under-sample (random, stratified, weighted)
│   └── cross_validator.py          # k-fold train/validation pairs
├── features/
│   ├── scaler.py                   # Standard or min-max scaling
│   ├── encoder.py                  # One-hot or ordinal encoding
│   ├── imputer.py                  # Missing-value imputation
│   ├── polynomial_features.py      # Interaction and polynomial features
│   ├── feature_selector.py         # Variance threshold or univariate selection
│   ├── embedding_extractor.py      # Text columns → embedding vectors via EmbeddingProvider
│   ├── image_embedding_extractor.py# Image bytes → vectors via ImageEncoderProvider
│   └── feature_store.py            # Read/write from FeatureStoreProvider
├── training/
│   ├── trainer.py                  # Fit any sklearn-compatible estimator → TrainedModel
│   ├── hyperparam_search.py        # Grid or random search → best TrainedModel
│   └── ensemble_builder.py         # Voting or stacking ensemble from TrainedModels
├── evaluation/
│   ├── evaluator.py                # Score TrainedModel on test split → EvalReport
│   ├── metric_gate.py              # Pass through only if metric >= threshold
│   ├── explainer.py                # Feature importances / SHAP values
│   └── fairness_audit.py           # Demographic parity, equalized odds, etc.
├── deployment/
│   ├── model_serializer.py         # Serialise TrainedModel → bytes via format string
│   ├── model_registrar.py          # Persist bytes + metadata to LineageStore
│   ├── predictor.py                # Batch inference from a loaded TrainedModel
│   └── shadow_deployer.py          # Champion/challenger routing; challenger not surfaced
├── assemblers/
│   ├── __init__.py
│   └── trained_model_object_store_assembler.py — bytes + ModelManifest → TrainedModelPayload
├── disassemblers/
│   ├── __init__.py
│   ├── trained_model_object_store_disassembler.py — TrainedModelPayload → bytes
│   ├── dataset_object_store_disassembler.py       — DatasetPayload → bytes
│   ├── data_split_object_store_disassembler.py    — DataSplitPayload → bytes
│   └── eval_report_database_disassembler.py       — EvalReportPayload → list[tuple]
└── specializations/                # Pre-built SubTapestry pipelines
    ├── task_pipelines/             # BinaryClassification, Multiclass, Regression, Forecasting, Nlp, ComputerVision,
    │                               # TimeSeriesForecasting, AnomalyDetection, CollaborativeFiltering,
    │                               # TextClassification, NamedEntityRecognition, ImageClassification,
    │                               # Clustering, DimensionalityReduction, ActiveLearningLoop
    ├── training/                   # SklearnTrainer, XgboostTrainer, NeuralNetTrainer,
    │                               # EarlyStopping, LRScheduler,
    │                               # BaggingEnsemble, StackingEnsemble, BlendingEnsemble,
    │                               # FineTuning, OnlineLearner, SemiSupervised, SelfSupervisedPretrainer
    ├── evaluation/                 # Classification, Regression, Ranking, Timeseries, WalkForward,
    │                               # ThresholdOptimizer, CalibrationFitter, ROCAUCAnalyzer,
    │                               # ConfusionMatrixAnalyzer, ResidualAnalyzer, PredictionIntervalEstimator,
    │                               # BacktestingEvaluator, RankingEvaluator, NLGEvaluator,
    │                               # FairnessAuditor, AdversarialRobustnessEvaluator
    ├── experiments/                # GridSearchTuner, BayesianSearchTuner, StratifiedKfold, AblationStudy,
    │                               # ChampionChallengerGate, KFoldCrossValidator, TimeSeriesCrossValidator,
    │                               # GroupKFoldCrossValidator, RandomSearchTuner, HyperbandTuner
    ├── feature_engineering/        # FeatureStoreReader/Writer, TextEmbedding, ImageEmbedding, LagFeatures,
    │                               # TargetEncoder, FrequencyEncoder, HashEncoder,
    │                               # RollingStatisticsGenerator, FourierFeatureGenerator,
    │                               # InteractionFeatureGenerator, TFIDFExtractor, NGramExtractor
    └── production/                 # FullTrainDeploy, ShadowDeployment, AbTest, ContinuousTraining,
                                    # DriftMonitor, ModelLineageTracker,
                                    # CanaryDeployer, ABTestDeployer,
                                    # DataDriftDetector, ConceptDriftDetector, PredictionDriftMonitor,
                                    # PerformanceTriggedRetrainer, BatchInferencePipeline,
                                    # SHAPExplainer, LIMEExplainer
```

---

## Assembler and Disassembler knots

ML artifacts cross the domain boundary through assembler and disassembler knots.

### Assembler

| Knot | Input | Output |
|------|-------|--------|
| `TrainedModelObjectStoreAssembler` | `bytes` + `ModelManifest` | `TrainedModelPayload` |

Receives raw bytes from an `ObjectStoreReadSource` and deserialises via joblib. Does not perform I/O.

### Disassemblers

| Knot | Input | Output | Destination |
|------|-------|--------|-------------|
| `TrainedModelObjectStoreDisassembler` | `TrainedModelPayload` | `bytes` | object store |
| `DatasetObjectStoreDisassembler` | `DatasetPayload` | `bytes` | object store |
| `DataSplitObjectStoreDisassembler` | `DataSplitPayload` | `bytes` | object store |
| `EvalReportDatabaseDisassembler` | `EvalReportPayload` | `list[tuple]` | database |

### Note on ModelRegistrar and Predictor

`ModelRegistrar` and `Predictor` are **not** assembler/disassembler knots — they are domain knots that own their I/O by design:

- `ModelRegistrar` — Sink that receives already-serialised bytes from `ModelSerializer` and writes them to an `ObjectStore`, logging lineage. The I/O is intentional and atomic.
- `Predictor` — Domain knot that loads a model and scores features. Owns its load path by design.

Do not replace these with disassemblers.

---

## Artifact formats and security

All format classes live in `pirn/domains/connectors/file_formats/`.

| Format | Class | Extra | Signer required | Notes |
|--------|-------|-------|-----------------|-------|
| ONNX | `OnnxFormat` | `pirn[onnx]` | No | Protobuf parser; no pickle path. `validate=True` (default) calls `onnx.checker.check_model`. Treat untrusted payloads as potentially triggering upstream library bugs. |
| SafeTensors | `SafetensorsFormat` | `pirn[safetensors]` | No | RCE-safe by design — no embedded code during deserialisation. `include_data=False` emits shape/dtype only, useful for large models. |
| Joblib | `JoblibFormat` | `pirn[joblib]` | Yes (or `allow_unsigned=True`) | Wraps pickle internally. HMAC-SHA256 signs before emit, verifies before load. `allow_unsigned=True` is dev/test only. |
| PyTorch | `PytorchFormat` | `pirn[pytorch]` | Yes (or `allow_unsigned=True`) | `torch.load` with `weights_only=False` is an RCE sink. Defaults to `weights_only=True`. Full model loading needs signer or `allow_unsigned=True`. |
| TF SavedModel | `TfSavedModelFormat` | `pirn[tensorflow]` | No | Zips the SavedModel directory on encode; extracts to temp dir on decode with path-traversal guards. Malicious models may embed arbitrary ops. |
| GGUF | `GgufFormat` | `pirn[gguf]` | No | llama.cpp quantised weights. No pickle path. Malformed payloads may trigger upstream parser bugs. |
| TFLite | `TfliteFormat` | `pirn[tflite]` | No | FlatBuffer format; falls back to `tensorflow.lite.Interpreter` when `tflite-runtime` is absent. Custom ops in malicious models are a risk. |

```python
from pirn.connectors.file_formats.safetensors_format import SafetensorsFormat
from pirn.connectors.file_formats.joblib_format import JoblibFormat
from pirn.backends._signer import _Signer

# SafeTensors — no signer required.
fmt = SafetensorsFormat(include_data=True)
records = list(await fmt.read(Path("model.safetensors").read_bytes()))
# records[0] keys: "tensors", "metadata", "tensor_count"

# Joblib — production: always use a signer.
signer = _Signer(secret=b"my-hmac-key")
fmt = JoblibFormat(signer=signer)
payload = await fmt.write([{"object": my_sklearn_pipeline}])

# Joblib — dev/test only.
fmt = JoblibFormat(allow_unsigned=True)
```

---

## Canonical pattern

Training pipeline: data prep → feature engineering → train → gate → serialise → register.

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.features.scaler import Scaler
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.evaluation.metric_gate import MetricGate
from pirn.domains.ml.deployment.model_serializer import ModelSerializer
from pirn.domains.ml.deployment.model_registrar import ModelRegistrar
from pirn.connectors.file_formats.joblib_format import JoblibFormat
from pirn.backends._signer import _Signer
from sklearn.linear_model import LogisticRegression

async def main():
    signer = _Signer(secret=b"prod-secret")

    with Tapestry() as t:
        dataset = DatasetLoader(
            source=Parameter("dataset_path", str),
            _config=KnotConfig(id="load"),
        )
        split = TrainTestSplit(dataset=dataset, test_size=0.2, stratify=True, _config=KnotConfig(id="split"))
        scaled = Scaler(split=split, strategy="standard", _config=KnotConfig(id="scale"))
        model = Trainer(split=scaled, estimator=LogisticRegression(max_iter=500), _config=KnotConfig(id="train"))
        report = Evaluator(model=model, split=scaled, _config=KnotConfig(id="eval"))
        gate = MetricGate(report=report, metric="f1", min_value=0.80, raise_on_fail=True, _config=KnotConfig(id="gate"))
        # `ModelSerializer` serialises metadata only. Wire a format connector (e.g. `JoblibFormat`) upstream to produce serialised bytes if you need to persist the estimator itself.
        serialized = ModelSerializer(model=model, format="joblib", _config=KnotConfig(id="serialize"))
        ModelRegistrar(serialized=serialized, lineage_store=my_mlflow_store, model_name="fraud-clf", _config=KnotConfig(id="register"))

    result = await t.run(RunRequest(parameters={"dataset_path": "data/train.csv"}))
    print(result.outputs["eval"])    # EvalReport
    print(result.outputs["gate"])    # True if f1 >= 0.80

asyncio.run(main())
```

For pre-built pipelines, prefer the specialisations:

```python
from pirn.domains.ml.specializations.task_pipelines.binary_classification_pipeline import (
    BinaryClassificationPipeline,
)

pipeline = BinaryClassificationPipeline(
    dataset=dataset_knot,
    estimator=LogisticRegression(),
    test_size=0.2,
    thresholds={"f1": 0.80},
    _config=KnotConfig(id="classify"),
)
```

For dynamic registry sweeps (e.g. evaluating N models in sequence without knowing N upfront), use `get_current_store()` inside `process()` to register successor knots at runtime and pass `extensible=True` to `t.run()`. See `examples/domain_formats/ml_evaluation_loop.py`.

---

## Anti-patterns

### Loading Joblib or PyTorch artifacts without a signer in production

`JoblibFormat(allow_unsigned=True)` and `PytorchFormat(allow_unsigned=True)` skip HMAC verification. Any tampered or malicious payload will be deserialised without warning. Reserve both flags for unit tests and local development only; production code must pass a `_Signer` instance.

### Using `ModelSerializer` expecting actual fitted-model bytes

The default `ModelSerializer.process()` serialises only the `TrainedModel` metadata fields (algorithm, hyperparameters, feature names) to JSON — it does not serialise the fitted estimator object. Subclass `ModelSerializer` and override `process()`, or use a format connector directly (`JoblibFormat`, `OnnxFormat`, etc.) alongside your own persistence logic.

To persist the fitted estimator itself, use a format connector (`JoblibFormat`, `SafetensorsFormat`, etc.) to serialise to bytes first, then pass the bytes to `ModelSerializer` or directly to `ModelRegistrar`.

### Using `TfSavedModelFormat` expecting a plain file path

`TfSavedModelFormat` ZIP-wraps the entire SavedModel directory on encode and extracts to a temporary directory on decode. Do not pass a file path directly to the format class; pass the raw bytes of the ZIP archive. The temp dir is cleaned up after decoding.

### Wiring `MetricGate` with a `thresholds` dict

`MetricGate` takes a single `metric: str` and `min_value: float`, not a dict of thresholds. To gate on multiple metrics, chain multiple `MetricGate` knots in series.

### Ignoring `EmbeddingProvider.close()` in long-running processes

`EmbeddingProvider`, `FeatureStoreProvider`, `ImageEncoderProvider`, and `LineageStore` all expose `close()`. Call it (or use an async context manager if the implementation provides one) to release connections and null credential references. Skipping `close()` leaks connections and leaves API keys in memory.

### Passing a `CrossValidator` output directly to `Trainer`

`CrossValidator` produces `k` fold pairs; `Trainer` expects a single `DataSplit`. Use `SklearnTrainerPipeline` or the `StratifiedKfoldValidator` specialisation which handles the fold loop internally.

---

## Constraints and gotchas

- **Lazy extras guard.** The core interfaces and types import without optional deps. Modules that use numpy/pandas/scikit-learn call `ExtrasLoader` at module top — the missing-extras error fires on first import of that module, not at install time. This means import errors surface at runtime inside a pipeline run if you forget `pip install pirn[ml]`.
- **`MetricGate` raises `KeyError` on unknown metric names.** The knot does not silently skip absent metrics — it raises. Ensure the metric key matches exactly what `Evaluator` puts in `EvalReport.metrics`.
- **`ShadowDeployer` does not surface the challenger result.** Challenger responses are logged to the `LineageStore` but not returned to callers. Do not use `ShadowDeployer` if you need the challenger result in your application logic.
- **`ModelRegistrar` depends on a `LineageStore` implementation.** There is no default built-in store. Wire in an MLflow, Weights & Biases, or custom `LineageStore` implementation before running.
- **Dynamic DAG expansion requires `extensible=True`.** When knots register successor knots at runtime via `get_current_store()`, call `await t.run(extensible=True)`. Without the flag, pirn treats the initial graph as final and will not resolve the dynamically registered knots.
- **`TrainTestSplit.stratify` requires a label column.** If `MLDataset.labels` is `None`, stratification raises at runtime — not at graph construction time.

---

## Quick reference

| Task | Knot / Format / Class |
|------|-----------------------|
| Load dataset | `DatasetLoader` |
| Train/test split | `TrainTestSplit` |
| k-fold cross-validation | `CrossValidator` |
| Scale features | `Scaler` |
| Encode categoricals | `Encoder` |
| Impute missing values | `Imputer` |
| Text embeddings | `EmbeddingExtractor` + `EmbeddingProvider` |
| Image embeddings | `ImageEmbeddingExtractor` + `ImageEncoderProvider` |
| Feature store I/O | `FeatureStore` + `FeatureStoreProvider` |
| Fit a model | `Trainer` |
| Hyperparameter search | `HyperparamSearch` |
| Ensemble | `EnsembleBuilder` |
| Evaluate model | `Evaluator` |
| Gate on a metric | `MetricGate` |
| Explain predictions | `Explainer` |
| Fairness audit | `FairnessAudit` |
| Serialise artifact (metadata) | `ModelSerializer` |
| Serialise sklearn/joblib artifact | `JoblibFormat` + `_Signer` |
| Serialise PyTorch artifact | `PytorchFormat` + `_Signer` |
| Serialise ONNX artifact | `OnnxFormat` |
| Serialise SafeTensors artifact | `SafetensorsFormat` |
| Register model with lineage | `ModelRegistrar` + `LineageStore` |
| Batch inference | `Predictor` |
| Champion/challenger routing | `ShadowDeployer` |
| Full train-to-deploy pipeline | `specializations/production/FullTrainDeployPipeline` |
| A/B test pipeline | `specializations/production/AbTestPipeline` |
| Drift monitoring | `specializations/production/DriftMonitor` |
| Dynamic multi-model evaluation | `get_current_store()` + `extensible=True` (see `ml_evaluation_loop.py`) |
| k-fold (plain) | `specializations/experiments/KFoldCrossValidator` |
| k-fold (time series) | `specializations/experiments/TimeSeriesCrossValidator` |
| k-fold (grouped) | `specializations/experiments/GroupKFoldCrossValidator` |
| Random hyperparameter search | `specializations/experiments/RandomSearchTuner` |
| Hyperband early-stopping search | `specializations/experiments/HyperbandTuner` |
| Frequency / hash encoding | `specializations/feature_engineering/FrequencyEncoder`, `HashEncoder` |
| Rolling window statistics | `specializations/feature_engineering/RollingStatisticsGenerator` |
| Fourier / interaction features | `specializations/feature_engineering/FourierFeatureGenerator`, `InteractionFeatureGenerator` |
| TF-IDF / n-gram extraction | `specializations/feature_engineering/TFIDFExtractor`, `NGramExtractor` |
| Early stopping | `specializations/training/EarlyStoppingTrainer` |
| LR scheduler training | `specializations/training/LRSchedulerTrainer` |
| Bagging / stacking / blending ensembles | `specializations/training/BaggingEnsembleBuilder`, `StackingEnsembleBuilder`, `BlendingEnsembleBuilder` |
| Fine-tuning pretrained model | `specializations/training/FineTuningTrainer` |
| Online / semi-supervised / self-supervised | `specializations/training/OnlineLearnerTrainer`, `SemiSupervisedTrainer`, `SelfSupervisedPretrainer` |
| Threshold optimisation | `specializations/evaluation/ThresholdOptimizer` |
| Calibration | `specializations/evaluation/CalibrationFitter` |
| ROC-AUC curve analysis | `specializations/evaluation/ROCAUCAnalyzer` |
| Confusion matrix analysis | `specializations/evaluation/ConfusionMatrixAnalyzer` |
| Residual analysis | `specializations/evaluation/ResidualAnalyzer` |
| Prediction intervals | `specializations/evaluation/PredictionIntervalEstimator` |
| Backtesting | `specializations/evaluation/BacktestingEvaluator` |
| NLG evaluation (BLEU / ROUGE) | `specializations/evaluation/NLGEvaluator` |
| Fairness audit | `specializations/evaluation/FairnessAuditor` |
| Adversarial robustness | `specializations/evaluation/AdversarialRobustnessEvaluator` |
| Canary deployment | `specializations/production/CanaryDeployer` |
| A/B test deployment | `specializations/production/ABTestDeployer` |
| Data drift detection | `specializations/production/DataDriftDetector` |
| Concept drift detection | `specializations/production/ConceptDriftDetector` |
| Prediction drift monitoring | `specializations/production/PredictionDriftMonitor` |
| Performance-triggered retraining | `specializations/production/PerformanceTriggeredRetrainer` |
| Batch inference pipeline | `specializations/production/BatchInferencePipeline` |
| SHAP explanations | `specializations/production/SHAPExplainer` |
| LIME explanations | `specializations/production/LIMEExplainer` |
| Time-series forecasting pipeline | `specializations/task_pipelines/TimeSeriesForecastingPipeline` |
| Anomaly detection pipeline | `specializations/task_pipelines/AnomalyDetectionPipeline` |
| Collaborative filtering pipeline | `specializations/task_pipelines/CollaborativeFilteringPipeline` |
| Text classification pipeline | `specializations/task_pipelines/TextClassificationPipeline` |
| Named entity recognition pipeline | `specializations/task_pipelines/NamedEntityRecognitionPipeline` |
| Image classification pipeline | `specializations/task_pipelines/ImageClassificationPipeline` |
| Clustering pipeline | `specializations/task_pipelines/ClusteringPipeline` |
| Dimensionality reduction pipeline | `specializations/task_pipelines/DimensionalityReductionPipeline` |
| Active learning loop | `specializations/task_pipelines/ActiveLearningLoop` |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
