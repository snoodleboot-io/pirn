`pirn_ml.specializations` provides pre-built machine learning pipeline patterns across training, evaluation, production deployment, experiments, feature engineering, and task pipelines — it does not provide model implementations; models are user-supplied as `Estimator` objects conforming to the ML tier interface.

---

## Mental model

ML specialization knots wrap the lifecycle of a model through its stages: feature preparation → training → evaluation → production. Each sub-package targets one stage. The `Estimator` interface (from `pirn_ml.knots`) is the common contract — any sklearn-compatible, PyTorch, or custom model that implements `fit()` / `predict()` works.

Use a `task_pipeline` for a complete end-to-end ML task (classification, forecasting, anomaly detection). Use individual stage sub-packages when you need to customize a specific stage.

---

## Sub-package index

| Sub-package | Stage | Contents |
|-------------|-------|---------|
| `training/` | Model training | Neural net trainer, fine-tuning, early stopping, online learning, ensemble builders |
| `evaluation/` | Model evaluation | Classification/regression evaluators, confusion matrix, bias detector, fairness auditor, calibration, adversarial robustness, backtesting |
| `experiments/` | Experiment tracking | Hyperparameter search (grid, Bayesian, Hyperband), cross-validation, ablation study, champion-challenger gate |
| `production/` | Production deployment | Batch inference, A/B test deployer, canary deployer, drift monitors (data + concept), continuous training |
| `feature_engineering/` | Feature preparation | Feature store reader/writer, embedding extractors, encoders, Fourier features |
| `task_pipelines/` | End-to-end task pipelines | Classification, forecasting, anomaly detection, clustering, collaborative filtering, computer vision, dimensionality reduction, active learning |

---

## Source map (production and task pipelines)

```
pirn_ml/specializations/
│
│  ── Production ──
├── production/
│   ├── batch_inference_pipeline.py      BatchInferencePipeline     — run model on a DataBatch; emit predictions
│   ├── ab_test_pipeline.py              AbTestPipeline             — split traffic; run two models; collect metrics
│   ├── ab_test_deployer.py              AbTestDeployer             — deploy A/B test configuration
│   ├── canary_deployer.py               CanaryDeployer             — ramp new model from 0–100% traffic
│   ├── data_drift_detector.py           DataDriftDetector          — detect input distribution shift
│   ├── concept_drift_detector.py        ConceptDriftDetector       — detect prediction accuracy degradation
│   ├── drift_monitor.py                 DriftMonitor               — combine data + concept drift signals
│   └── continuous_training_pipeline.py  ContinuousTrainingPipeline — trigger retraining on drift signal
│
│  ── Task pipelines ──
├── task_pipelines/
│   ├── binary_classification_pipeline.py  BinaryClassificationPipeline  — features → train → evaluate
│   ├── forecasting_pipeline.py            ForecastingPipeline            — time-series forecast pipeline
│   ├── anomaly_detection_pipeline.py      AnomalyDetectionPipeline       — score + threshold anomalies
│   ├── clustering_pipeline.py             ClusteringPipeline             — cluster + label records
│   ├── collaborative_filtering_pipeline.py CollaborativeFilteringPipeline — recommendation pipeline
│   ├── computer_vision_pipeline.py        ComputerVisionPipeline         — image → features → model
│   ├── dimensionality_reduction_pipeline.py DimensionalityReductionPipeline — PCA/UMAP/t-SNE
│   └── active_learning_loop.py            ActiveLearningLoop             — query strategy + labeling loop
│
│  ── Experiments ──
├── experiments/
│   ├── grid_search_tuner.py             GridSearchTuner            — exhaustive hyperparameter search
│   ├── bayesian_search_tuner.py         BayesianSearchTuner        — Bayesian optimization search
│   ├── hyperband_tuner.py               HyperbandTuner             — Hyperband early-stopping search
│   ├── group_kfold_cross_validator.py   GroupKFoldCrossValidator   — group-aware k-fold CV
│   ├── ablation_study_pipeline.py       AblationStudyPipeline      — systematic feature ablation
│   ├── champion_challenger_check.py     ChampionChallengerCheck    — compare challenger vs champion metrics
│   └── champion_challenger_gate.py      ChampionChallengerGate     — Gate: pass if challenger wins; Err otherwise
```

---

## Canonical pattern

### Batch inference in production

```python
from pirn_ml.specializations.production.batch_inference_pipeline import BatchInferencePipeline
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    features   = Parameter("features", DataBatch)
    predictions = BatchInferencePipeline(
        features=features,
        model=my_model,
        output_column="score",
        _config=KnotConfig(id="infer"),
    )
    SinkKnot(data=predictions, _config=KnotConfig(id="sink"))
```

### Drift monitoring — alert on data drift

```python
from pirn_ml.specializations.production.drift_monitor import DriftMonitor

with Tapestry() as t:
    features = FeatureSource(_config=KnotConfig(id="features"))
    DriftMonitor(
        features=features,
        reference_dataset=my_reference_batch,
        threshold=0.05,
        alert_client=my_slack_client,
        _config=KnotConfig(id="drift"),
    )
```

### Bayesian hyperparameter search

```python
from pirn_ml.specializations.experiments.bayesian_search_tuner import BayesianSearchTuner

with Tapestry() as t:
    train_data = TrainSource(_config=KnotConfig(id="train"))
    best_model = BayesianSearchTuner(
        data=train_data,
        estimator_class=MyModel,
        param_space={"lr": (1e-4, 1e-1), "depth": (3, 10)},
        n_trials=50,
        _config=KnotConfig(id="tune"),
    )
```

---

## Anti-patterns

**Using `BinaryClassificationPipeline` without a held-out test set** — the pipeline trains and evaluates on the same data if only one dataset is provided. Always pass separate `train_data` and `eval_data` parameters.

**Running `ContinuousTrainingPipeline` on every detected drift event** — spurious drift signals cause unnecessary retraining. Use the pipeline with a `min_drift_duration` window to require sustained drift before triggering.

---

## Constraints and gotchas

- **All pipelines require `pirn[ml]` and the relevant model library** (e.g. `pirn[torch]`, `pirn[sklearn]`).
- **`CanaryDeployer` manages traffic weights externally** — it emits a weight configuration; the serving layer (model server, feature flag system) must apply it. pirn does not serve models.
- **`ChampionChallengerGate` is a `Gate`** — if the challenger does not beat the champion metric, it emits `Err`, stopping the downstream promote-to-production knot chain.
- **`ActiveLearningLoop` iterates within a single tapestry run.** Set `max_iterations` to bound the number of query-label cycles per run.

---

## Quick reference

| Task | Entry point |
|------|------------|
| Run model on batch | `BatchInferencePipeline(features=..., model=...)` |
| Monitor for data drift | `DriftMonitor(features=..., reference_dataset=...)` |
| A/B test two models | `AbTestPipeline(model_a=..., model_b=..., traffic_split=0.1)` |
| Tune hyperparameters | `BayesianSearchTuner` / `GridSearchTuner` / `HyperbandTuner` |
| Full classification pipeline | `BinaryClassificationPipeline` |
| Time-series forecasting | `ForecastingPipeline` |
| Anomaly detection | `AnomalyDetectionPipeline` |
| Evaluate fairness | `FairnessAuditor` (in `evaluation/`) |

---

*See also: [ml AGENTIC_USE.md](../AGENTIC_USE.md)*
