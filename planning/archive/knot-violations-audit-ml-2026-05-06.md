# Knot Design Rules Audit Report

**Scan Date:** 2026-05-06  
**Method:** Automated AST scan, all rules R1-R11 + Security

## Legend

| Column | Rule | Details |
|--------|------|---------|
| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |
| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |
| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |
| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |
| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |
| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |
| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |
| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |
| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |
| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |
| R10-Math | Module docstring contains `Math:` section | Always required — N/A confirmed only after reading `process()` |
| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |
| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |
| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |
| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |

**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply

---

## Audit Table

### Group 1 — data_prep/cross_validator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/data_prep/cross_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 2 — data_prep/dataset_loader.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/data_prep/dataset_loader.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 3 — data_prep/sampler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/data_prep/sampler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 4 — data_prep/train_test_split.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/data_prep/train_test_split.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 5 — deployment/model_registrar.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/deployment/model_registrar.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 6 — deployment/model_serializer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/deployment/model_serializer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 7 — deployment/predictor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/deployment/predictor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 8 — deployment/shadow_deployer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/deployment/shadow_deployer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 9 — evaluation/evaluator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/evaluation/evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 10 — evaluation/explainer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/evaluation/explainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 11 — evaluation/fairness_audit.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/evaluation/fairness_audit.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 12 — evaluation/metric_gate.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/evaluation/metric_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 13 — features/embedding_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/embedding_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 14 — features/encoder.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/encoder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 15 — features/feature_selector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/feature_selector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 16 — features/feature_store.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/feature_store.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 17 — features/image_embedding_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/image_embedding_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 18 — features/imputer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/imputer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 19 — features/polynomial_features.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/polynomial_features.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 20 — features/scaler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/features/scaler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 21 — specializations/evaluation

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/specializations/evaluation/adversarial_robustness_evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/backtesting_evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/bias_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/calibration_fitter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/classification_eval_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/confusion_matrix_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/fairness_auditor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/nlg_evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/prediction_interval_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/ranking_eval_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/ranking_evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/regression_eval_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/residual_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/roc_auc_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/threshold_optimizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/timeseries_eval_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/evaluation/walk_forward_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 22 — specializations/experiments

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/specializations/experiments/ablation_study_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/baseline_establisher.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/bayesian_search_tuner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/champion_challenger_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/grid_search_tuner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/group_kfold_cross_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/hyperband_tuner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/kfold_cross_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/random_search_tuner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/stratified_kfold_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/time_series_cross_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/experiments/time_series_splitter_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 23 — specializations/feature_engineering

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/specializations/feature_engineering/_feature_store_reader_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/_image_encoder_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/_lag_append_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/feature_store_reader.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/feature_store_writer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/fourier_feature_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/frequency_encoder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/hash_encoder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/image_embedding_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/interaction_feature_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/lag_feature_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/ngram_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/rolling_statistics_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/target_encoder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/text_embedding_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/feature_engineering/tfidf_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 24 — specializations/production

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/specializations/production/ab_test_deployer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/ab_test_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/batch_inference_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/canary_deployer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/concept_drift_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/continuous_training_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/data_drift_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/drift_monitor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/full_train_deploy_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/lime_explainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/model_lineage_tracker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/performance_triggered_retrainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/prediction_drift_monitor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/shadow_deployment_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/production/shap_explainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 25 — specializations/task_pipelines

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/specializations/task_pipelines/active_learning_loop.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/anomaly_detection_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/binary_classification_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/clustering_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/collaborative_filtering_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/computer_vision_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/dimensionality_reduction_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/forecasting_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/image_classification_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/multiclass_classification_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/named_entity_recognition_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/nlp_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/regression_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/text_classification_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/task_pipelines/time_series_forecasting_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 26 — specializations/training

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/specializations/training/bagging_ensemble_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/blending_ensemble_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/early_stopping_trainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/fine_tuning_trainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/lr_scheduler_trainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/neural_net_trainer_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/online_learner_trainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/self_supervised_pretrainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/semi_supervised_trainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/sklearn_trainer_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/stacking_ensemble_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |
| `pirn/domains/ml/specializations/training/xgboost_trainer_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 27 — training/ensemble_builder.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/training/ensemble_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 28 — training/hyperparam_search.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/training/hyperparam_search.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |

### Group 29 — training/trainer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/ml/training/trainer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | N/A | N/A | [x] | [x] |
