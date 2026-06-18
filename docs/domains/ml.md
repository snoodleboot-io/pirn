# ML domain

The ML domain (`pirn_ml/`) provides knots and interfaces that cover the full machine learning lifecycle: data preparation, feature engineering, training, evaluation, deployment, and lineage tracking. Each stage is a typed, async knot — composable, observable, and content-addressed out of the box.

```bash
pip install 'pirn-ml[ml]'
```

`pirn_ml` is a standalone distribution. Its `ml` extra pulls `numpy`, `pandas`, and `scikit-learn`. Training backends, deep learning frameworks, and feature stores are user-supplied; pirn only defines the interfaces they must satisfy.

Available extras: `ml`. `pirn_ml` depends on both `pirn-core` and `pirn-data` — it consumes `DataBatch` / `LakehouseTable` / `FileSource` / `SqlSource` from `pirn_data` (the one retained domain→domain edge, ADR-3), so installing `pirn-ml` pulls `pirn-data` automatically.

**Registration (ADR-4):** `import pirn_ml` self-registers the ML-domain knots under `library="pirn"`, so a YAML pipeline can resolve them by bare name. In Python you import the knot classes directly (same effect). To register every installed domain at once, call `pirn.discover_installed_domains()`.

!!! warning "Legacy `pirn.domains.ml` is deprecated"
    The old `pirn.domains.ml` import path still works for one deprecation cycle via a compat shim (it emits a `DeprecationWarning` and defers to `pirn_ml`). Migrate to `pirn_ml` — see the [migration guide](../guides/migrating-to-split-packages.md).

---

## Overview

The ML lifecycle maps directly to pirn's knot taxonomy:

```
DatasetLoader → TrainTestSplit → Scaler → Encoder → Trainer → Evaluator → ModelRegistrar → Predictor
                                                         ↑
                                              HyperparamSearch / EnsembleBuilder
```

Each box is a knot. Wire them inside a `Tapestry` context and pirn handles execution order, content-addressed lineage, and result routing. Swap any knot for a different implementation without touching the rest of the pipeline.

---

## ML artifact formats

ML models are whole-artifact blobs — not row-oriented tables. The connector layer treats each artifact as one record and surfaces metadata alongside the bytes. All ML format classes live on core's connector surface under `pirn.connectors.file_formats.*` (they are part of core, not the ML domain).

| Format | Class | Extra | Security properties |
|--------|-------|-------|---------------------|
| ONNX | `OnnxFormat` | `pirn[onnx]` | Protobuf parser; no pickle path. `validate=True` (default) runs `onnx.checker.check_model`. Treat untrusted payloads as potentially triggering upstream library bugs. |
| SafeTensors | `SafetensorsFormat` | `pirn[safetensors]` | RCE-safe by design — no embedded code path during deserialisation. No signer required. `include_data=False` emits only shape/dtype metadata for large models. |
| Joblib | `JoblibFormat` | `pirn[joblib]` | **Uses pickle internally.** Constructor refuses unsigned construction: pass a `_Signer` (production) or `allow_unsigned=True` (dev/test only). With a signer, payloads are HMAC-SHA256 signed before emission and verified before `joblib.load`. |
| PyTorch | `PytorchFormat` | `pirn[pytorch]` | `torch.load` with `weights_only=False` is an RCE sink. Constructor defaults `weights_only=True` (safe-mode, restores tensor data only). Full model loading requires a `_Signer` (HMAC-SHA256 verified before deserialisation) or `allow_unsigned=True`. |
| TF SavedModel | `TfSavedModelFormat` | `pirn[tensorflow]` | Zips the SavedModel directory on encode; extracts to a temp dir on decode. ZIP extraction guards against path-traversal members. Malicious SavedModels may contain arbitrary ops — treat untrusted payloads accordingly. |
| GGUF | `GgufFormat` | `pirn[gguf]` | llama.cpp quantised LLM weights. Generally robust parser; malformed payloads may trigger upstream bugs. No pickle path. |
| TFLite | `TfliteFormat` | `pirn[tflite]` | FlatBuffer format; falls back to `tensorflow.lite.Interpreter` if `tflite-runtime` is absent. Malicious models may contain custom ops — treat untrusted payloads accordingly. |

### Using ML format connectors

```python
from pirn.connectors.file_formats.safetensors_format import SafetensorsFormat
from pirn.connectors.file_formats.joblib_format import JoblibFormat
from pirn.backends._signer import _Signer

# SafeTensors — no signer needed.
fmt = SafetensorsFormat(include_data=True)
records = list(await fmt.read(Path("model.safetensors").read_bytes()))
# records[0] keys: "tensors", "metadata", "tensor_count"

# Joblib — signer required for production.
signer = _Signer(secret=b"my-hmac-key")
fmt = JoblibFormat(signer=signer)
payload = await fmt.write([{"object": my_sklearn_pipeline}])

# Joblib — dev/test without a signer.
fmt = JoblibFormat(allow_unsigned=True)
```

---

## Provider interfaces

### EmbeddingProvider

`EmbeddingProvider` (`pirn/core/providers/embedding_provider.py`) is the interface for text embedding backends. Implement `embed` and `close`:

| Method | Signature | Description |
|--------|-----------|-------------|
| `embed` | `(texts: Sequence[str], *, model: str \| None) -> list[list[float]]` | Return one embedding vector per input string, in input order. |
| `close` | `() -> None` | Release underlying connections. Call `_clear_credentials()` to null API key. |

```python
from pirn.core.providers.embedding_provider import EmbeddingProvider

class OpenAIEmbedder(EmbeddingProvider):
    def __init__(self, api_key: str) -> None:
        import openai
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._config = api_key

    async def embed(self, texts, *, model=None):
        resp = await self._client.embeddings.create(
            input=list(texts),
            model=model or "text-embedding-3-small",
        )
        return [item.embedding for item in resp.data]

    async def close(self) -> None:
        await self._client.close()
        self._clear_credentials()
```

### FeatureStoreProvider

`FeatureStoreProvider` (`pirn_ml/feature_store_provider.py`) wraps online or offline feature stores (Feast, Tecton, custom catalogs):

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_features` | `(entity_keys, feature_names) -> list[Mapping[str, Any]]` | Return one feature row per entity key in input order. |
| `write_features` | `(features: Iterable[Mapping[str, Any]]) -> int` | Persist computed feature rows. Returns the count written. |
| `close` | `() -> None` | Release underlying connections. |

### ImageEncoderProvider

`ImageEncoderProvider` (`pirn_ml/image_encoder_provider.py`) wraps image embedding models (CLIP, ResNet via remote API, etc.):

| Method | Signature | Description |
|--------|-----------|-------------|
| `encode` | `(images: Sequence[bytes], *, model: str \| None) -> list[list[float]]` | Return one embedding vector per image, in input order. |
| `close` | `() -> None` | Release underlying connections. |

### LineageStore

`LineageStore` (`pirn_ml/lineage_store.py`) wraps ML registries (MLflow, Weights & Biases, custom catalogs):

| Method | Signature | Description |
|--------|-----------|-------------|
| `log_event` | `(event_type, payload)` | Record a lineage event — training run, evaluation, or deployment. |
| `fetch_lineage` | `(model_id) -> Mapping[str, Any]` | Return the full recorded lineage chain for `model_id`. |
| `close` | `() -> None` | Release underlying connections. |

---

## Sub-packages

### `data_prep/`

Knots for preparing datasets before training.

| Knot | Description |
|------|-------------|
| `DatasetLoader` | Loads a dataset from a `FeatureStoreProvider` or a plain `MLDataset`. |
| `TrainTestSplit` | Splits a dataset into training and test `DataSplit`s. Supports stratification. |
| `Sampler` | Over- or under-samples a dataset split (random, stratified, or weighted). |
| `CrossValidator` | Produces `k` train/validation fold pairs from a dataset. |

### `features/`

Knots for feature engineering.

| Knot | Description |
|------|-------------|
| `Scaler` | Standard or min-max scaling via scikit-learn. |
| `Encoder` | One-hot or ordinal encoding for categorical columns. |
| `Imputer` | Missing-value imputation (mean, median, most-frequent, constant). |
| `PolynomialFeatures` | Generates interaction and polynomial features. |
| `FeatureSelector` | Selects features by variance threshold or univariate test. |
| `EmbeddingExtractor` | Calls an `EmbeddingProvider` to embed text columns; appends vectors to the dataset. |
| `ImageEmbeddingExtractor` | Calls an `ImageEncoderProvider` to embed image bytes; appends vectors to the dataset. |
| `FeatureStore` | Reads from or writes to a `FeatureStoreProvider`. |

### `training/`

Knots for fitting models.

| Knot | Description |
|------|-------------|
| `Trainer` | Fits a scikit-learn-compatible estimator on a `DataSplit`. Returns a `TrainedModel`. |
| `HyperparamSearch` | Grid or random search over a parameter grid. Returns the best `TrainedModel`. |
| `EnsembleBuilder` | Builds a voting or stacking ensemble from multiple `TrainedModel`s. |

### `evaluation/`

Knots for measuring model performance.

| Knot | Description |
|------|-------------|
| `Evaluator` | Scores a `TrainedModel` on a test split. Returns an `EvalReport`. |
| `MetricCheck` | Checks whether a named metric in an `EvalReport` meets a minimum threshold; raises on failure if configured to do so. |
| `Explainer` | Computes feature importances or SHAP values. |
| `FairnessAudit` | Computes demographic parity, equalized odds, and other fairness metrics across protected groups. |

### `deployment/`

Knots for registering and serving models.

| Knot | Description |
|------|-------------|
| `ModelSerializer` | Serialises a `TrainedModel` to bytes using an ML format connector. |
| `ModelRegistrar` | Persists model bytes and metadata to a `LineageStore`. |
| `Predictor` | Runs inference from a loaded `TrainedModel` on a batch of inputs. |
| `ShadowDeployer` | Routes traffic to both a champion and a challenger model; logs both responses without surfacing the challenger result to callers. |

### `specializations/`

Pre-built `SubTapestry` pipelines for common ML patterns.

| Sub-area | Pipelines |
|----------|-----------|
| `task_pipelines/` | `BinaryClassificationPipeline`, `MulticlassClassificationPipeline`, `RegressionPipeline`, `ForecastingPipeline`, `NlpPipeline`, `ComputerVisionPipeline` |
| `training/` | `SklearnTrainerPipeline`, `XgboostTrainerPipeline`, `NeuralNetTrainerPipeline` |
| `evaluation/` | `ClassificationEvalPipeline`, `RegressionEvalPipeline`, `RankingEvalPipeline`, `TimeseriesEvalPipeline`, `WalkForwardValidator` |
| `experiments/` | `GridSearchTuner`, `BayesianSearchTuner`, `StratifiedKfoldValidator`, `TimeSeriesSplitterValidator`, `AblationStudyPipeline`, `ChampionChallengerGate` |
| `feature_engineering/` | `FeatureStoreReader`, `FeatureStoreWriter`, `TextEmbeddingExtractor`, `ImageEmbeddingExtractor`, `LagFeatureGenerator`, `TargetEncoder` |
| `production/` | `FullTrainDeployPipeline`, `ShadowDeploymentPipeline`, `AbTestPipeline`, `ContinuousTrainingPipeline`, `DriftMonitor`, `ModelLineageTracker` |

---

## Types

| Type | Description |
|------|-------------|
| `MLDataset` | Holds feature and label arrays (pandas `DataFrame` + optional `Series`). |
| `DataSplit` | A train/test or train/validation split of an `MLDataset`. |
| `TrainedModel` | Wraps a fitted estimator alongside its feature names, training metrics, and serialisation metadata. |
| `EvalReport` | Metric dict, confusion matrix, per-class report, and a pass/fail flag against thresholds. |

---

## Code examples

### Binary classification pipeline

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.data_prep.train_test_split import TrainTestSplit
from pirn_ml.features.scaler import Scaler
from pirn_ml.training.trainer import Trainer
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.evaluation.metric_gate import MetricCheck

from sklearn.linear_model import LogisticRegression

async def main():
    with Tapestry() as t:
        raw_data = Parameter("dataset_path", str)

        dataset = DatasetLoader(
            source=raw_data,
            _config=KnotConfig(id="load"),
        )
        split = TrainTestSplit(
            dataset=dataset,
            test_size=0.2,
            stratify=True,
            _config=KnotConfig(id="split"),
        )
        scaled = Scaler(
            split=split,
            strategy="standard",
            _config=KnotConfig(id="scale"),
        )
        model = Trainer(
            split=scaled,
            estimator=LogisticRegression(max_iter=500),
            _config=KnotConfig(id="train"),
        )
        report = Evaluator(
            model=model,
            split=scaled,
            _config=KnotConfig(id="eval"),
        )
        check = MetricCheck(
            report=report,
            metric="f1",
            min_value=0.80,
            raise_on_fail=True,
            _config=KnotConfig(id="check"),
        )

    result = await t.run(
        RunRequest(parameters={"dataset_path": "data/train.csv"})
    )
    print(result.outputs["eval"])   # EvalReport
    print(result.outputs["check"])  # True if f1 >= 0.80

asyncio.run(main())
```

### Registering a model with lineage tracking

```python
from pirn_ml.deployment.model_serializer import ModelSerializer
from pirn_ml.deployment.model_registrar import ModelRegistrar
from pirn.connectors.file_formats.joblib_format import JoblibFormat
from pirn.backends._signer import _Signer

signer = _Signer(secret=b"my-secret")

serializer = ModelSerializer(
    model=model_knot,
    format=JoblibFormat(signer=signer),
    _config=KnotConfig(id="serialize"),
)
registrar = ModelRegistrar(
    serialized=serializer,
    lineage_store=my_mlflow_store,
    model_name="fraud-classifier",
    _config=KnotConfig(id="register"),
)
```

### Using pre-built task pipelines

```python
from pirn_ml.specializations.task_pipelines.binary_classification_pipeline import (
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

---

## Connector boundaries

Domain payloads enter and leave the ML domain through assembler/disassembler knots.

**Assembler** (raw → Payload, no I/O):

| Assembler | Input | Output |
|-----------|-------|--------|
| `TrainedModelObjectStoreAssembler` | `bytes` from object store | `TrainedModelPayload` |

**Disassemblers** (Payload → raw, no I/O):

| Disassembler | Input | Output |
|--------------|-------|--------|
| `TrainedModelObjectStoreDisassembler` | `TrainedModelPayload` | `bytes` |
| `DatasetObjectStoreDisassembler` | `MLDataset` | `bytes` |
| `DataSplitObjectStoreDisassembler` | `DataSplit` | `bytes` |
| `EvalReportDatabaseDisassembler` | `EvalReport` | `list[tuple]` |

All assemblers and disassemblers live under `pirn_ml/assemblers/` and `pirn_ml/disassemblers/` respectively.

**Note:** `ModelRegistrar` and `Predictor` are kept as-is — they own I/O by design. `ModelRegistrar` persists model bytes and metadata to a `LineageStore`; `Predictor` runs inference. These are not assembler/disassembler knots.

---

## Install

```bash
# Core ML domain (pulls pirn-core + pirn-data automatically).
pip install 'pirn-ml[ml]'

# Add specific artifact format support (these are pirn-core connector extras):
pip install pirn[onnx]          # ONNX validation
pip install pirn[safetensors]   # Hugging Face safetensors
pip install pirn[joblib]        # scikit-learn / joblib persistence
pip install pirn[pytorch]       # PyTorch state dicts
pip install pirn[tensorflow]    # TF SavedModel + TFLite fallback
pip install pirn[gguf]          # llama.cpp quantised weights
pip install pirn[tflite]        # TFLite runtime (lighter than full TF)
```

**See also:** [Connectors — Format Matrix](../connectors/index.md), [Concepts](../getting-started/concepts.md)
