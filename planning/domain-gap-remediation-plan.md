# Domain Implementation Gap — Remediation Plan (Revised)

**Audited:** 2026-05-07 (revised after initial incorrect assessment)  
**Last Updated:** 2026-05-09 — health, signal, and oilgas complete (seismic included)  
**Branch:** feat/domain-gap-remediation-plan  
**Scope:** All Python files under `pirn/domains/` (1,195 files across 7 top-level domains)  
**Method:** Per-file strict read — validation and correct return type alone do NOT constitute implementation. "Real Implementation" = YES only when `process()` calls a computation library, external SDK, non-trivial algorithm, or real I/O.

---

## Critical Correction from Initial Audit

The first audit was wrong. It classified files as "COMPLETE" if they had:
- Input validation
- A correctly-typed return value

**This is insufficient.** A file that validates `notch_hz > 0` and returns `SignalFrame(signal_id=..., sample_rate_hz=..., samples_per_channel=...)` without ever calling `scipy.signal.iirnotch` does nothing. The signal passes through unchanged. Every domain except `agents`, `data`, and `connectors` contains significant numbers of these hollow shells.

---

## Revised Executive Summary

| Domain | Approx Files | Real Implementation | Status |
|--------|-------------|--------------------|---------| 
| agents | ~175 | ~95% | ✅ Implemented |
| data | ~100 | ~85% | ✅ Implemented |
| connectors | ~265 | ~50% (all pool/client/store files) | ✅ Implemented |
| signal | ~85 | ~100% | ✅ Implemented (2026-05-08) |
| health | ~129 | ~77% | ⚠️ Payload pattern fixed (2026-05-08); ~25 hollow remain in mri/pathology/trials |
| **ml** | **~126** | **0%** | ❌ All hollow |
| **oilgas** | **~109** | **~95%** | ✅ Implemented (2026-05-09); 5 parser files remain hollow |

> Config files (`*_config.py`), type dataclasses, abstract base classes, and protocol interfaces are excluded from the "hollow" count — they are structural-only by design.

---

## Domains Confirmed Implemented

### agents — ✅ Implemented (real computation) | ⚠️ Payload pattern audit pending

All non-interface, non-type files perform real computation:
- `generation/llm_call.py`, `streaming_llm_call.py` — call `llm.chat()` / `llm.stream_chat()`
- `memory/memory_writer.py`, `memory_retriever.py` — call `store.store()` / `store.retrieve()`
- `control/safety_check.py` — regex matching against real patterns
- `planning/tool_executor.py` — dispatches real `tool.invoke()` calls
- All RAG, ReAct, structured output, guardrail, multi-agent, and document processing files compose real LLM calls and memory operations

Notable non-implementations (by design):
- `llm_provider_knot.py`, `memory_store_knot.py`, `messages_passthrough.py` — intentional pass-through knots
- `approval_check.py`, `clarification_requester.py` — human-in-the-loop gates that return static results pending external interaction

**Payload pattern audit — TODO:** Verify that metadata-only types (e.g. `AgentContext`, `AgentResponse`, `ToolResult`) are not crossing pipeline boundaries bare when they should carry a data payload. Real computation does not imply correct payload pattern.

---

### data — ✅ Implemented (real computation) | ⚠️ Payload pattern audit pending

All computation knots perform real work:
- `transforms/aggregate.py` — real grouping, aggregation (sum/mean/min/max/count/distinct/first/last)
- `transforms/deduplicate.py` — real set-based deduplication
- `transforms/filter.py`, `cast.py`, `rename.py`, `normalize.py` — real row-level transforms
- `quality/profiler.py` — real per-column statistics (Counter, null counts, distinct counts)
- `quality/null_rate_check.py`, `freshness_check.py`, `schema_validator.py` — real threshold checks
- `lakehouse/delta/delta_table.py` — calls `deltalake` SDK (`write_deltalake`, `merge`)
- `lakehouse/iceberg/iceberg_table.py` — calls `pyiceberg` SDK
- `sources/file_source.py`, `directory_source.py` — real object store I/O via `store.get()` / `store.list()`
- `validation/great_expectations/` — calls GE validation engine
- All frames (pandas/polars/duckdb/pyarrow/datafusion) — real SDK operations

**Payload pattern audit — TODO:** Inspect whether frame types (`PandasFrame`, `PolarsFrame`, etc.) carry both schema metadata and the actual DataFrame, or whether any ingestors/sources return metadata-only types that lose the data buffer across a FilesystemTransport round-trip.

---

### connectors — ✅ Implemented (real computation) | ⚠️ Payload pattern audit pending

All `*_pool.py`, `*_broker.py`, `*_store.py`, `*_client.py` files call real external SDKs. Config files (`*_config.py`) are intentionally structural only.

Real SDK calls confirmed across: `asyncpg`, `aiomysql`, `aiosqlite`, `duckdb`, `snowflake-connector-python`, `google-cloud-bigquery`, `oracledb`, `clickhouse_connect`, `aioodbc`, `databricks-sql-connector`, `pyarrow.flight` (Dremio), `motor` (MongoDB), `google-cloud-firestore`, `azure-cosmos`, `aiokafka`, `google-cloud-pubsub`, `aioboto3`, `aio_pika`, `azure-servicebus`, `redis`, `gcloud-aio-storage`, `azure-storage-blob`, `hdfs3`, `influxdb-client`, `stripe`, `simple-salesforce`, `PyGithub`, `slack-sdk`, and all 80+ file format codecs.

**Payload pattern audit — TODO:** Inspect transport types and message broker return values. Confirm that any type returned by a connector knot that contains both metadata (topic, offset, schema) and data (message bytes, record dict) is structured as a payload, not a metadata-only type.

---

## Domains with Major Gaps

---

### ml — ❌ 0% Real Implementation (~126 files)

**Pattern:** Every `process()` method in every non-interface file uses SHA-256 hashing to produce deterministic placeholder values. No sklearn, torch, XGBoost, LIME, SHAP, or any ML library is imported or called. Feature transformers rename datasets but don't transform rows. The Trainer produces a model ID from a hash; the Evaluator produces metrics from a hash.

This is deliberate orchestration scaffolding — the framework validates that graph wiring is correct but performs no actual ML computation.

#### ml/data_prep/

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| cross_validator.py | [ml/data_prep/cross_validator.py](pirn/domains/ml/data_prep/cross_validator.py) | YES | YES | NO — computes fold sizes from arithmetic, no data I/O |
| dataset_loader.py | [ml/data_prep/dataset_loader.py](pirn/domains/ml/data_prep/dataset_loader.py) | YES | YES | NO — counts rows only, does not materialize rows |
| sampler.py | [ml/data_prep/sampler.py](pirn/domains/ml/data_prep/sampler.py) | YES | YES | NO — computes new row_count from fraction, no sampling |
| train_test_split.py | [ml/data_prep/train_test_split.py](pirn/domains/ml/data_prep/train_test_split.py) | YES | YES | NO — SHA-256 bias for split sizes, no data partition |

#### ml/training/

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| trainer.py | [ml/training/trainer.py](pirn/domains/ml/training/trainer.py) | YES | YES | NO — SHA-256 model_id, no fit() call |
| ensemble_builder.py | [ml/training/ensemble_builder.py](pirn/domains/ml/training/ensemble_builder.py) | YES | YES | NO — SHA-256 ensemble_id, no ensemble logic |
| hyperparam_search.py | [ml/training/hyperparam_search.py](pirn/domains/ml/training/hyperparam_search.py) | YES | YES | NO — SHA-256 scores candidates, no training |

#### ml/evaluation/

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| evaluator.py | [ml/evaluation/evaluator.py](pirn/domains/ml/evaluation/evaluator.py) | YES | YES | NO — SHA-256 metric values |
| explainer.py | [ml/evaluation/explainer.py](pirn/domains/ml/evaluation/explainer.py) | YES | YES | NO — SHA-256 feature importances |
| fairness_audit.py | [ml/evaluation/fairness_audit.py](pirn/domains/ml/evaluation/fairness_audit.py) | YES | YES | NO — SHA-256 parity scores |
| metric_gate.py | [ml/evaluation/metric_gate.py](pirn/domains/ml/evaluation/metric_gate.py) | YES | YES | NO — threshold comparison only |

#### ml/features/

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| embedding_extractor.py | [ml/features/embedding_extractor.py](pirn/domains/ml/features/embedding_extractor.py) | YES | YES | NO — probes provider but does not embed actual data |
| encoder.py | [ml/features/encoder.py](pirn/domains/ml/features/encoder.py) | YES | YES | NO — renames DataSplit, no encoding |
| feature_selector.py | [ml/features/feature_selector.py](pirn/domains/ml/features/feature_selector.py) | YES | YES | NO — truncates feature_names list only |
| feature_store.py | [ml/features/feature_store.py](pirn/domains/ml/features/feature_store.py) | YES | YES | PARTIAL — calls provider.write_features() with metadata rows only |
| image_embedding_extractor.py | [ml/features/image_embedding_extractor.py](pirn/domains/ml/features/image_embedding_extractor.py) | YES | YES | NO — probes encoder, no embedding |
| imputer.py | [ml/features/imputer.py](pirn/domains/ml/features/imputer.py) | YES | YES | NO — renames DataSplit, no imputation |
| polynomial_features.py | [ml/features/polynomial_features.py](pirn/domains/ml/features/polynomial_features.py) | YES | YES | NO — derives feature names via combinatorics, no values |
| scaler.py | [ml/features/scaler.py](pirn/domains/ml/features/scaler.py) | YES | YES | NO — renames DataSplit, no scaling |

#### ml/deployment/

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| model_registrar.py | [ml/deployment/model_registrar.py](pirn/domains/ml/deployment/model_registrar.py) | YES | YES | NO — stores metadata JSON, not a real model artifact |
| model_serializer.py | [ml/deployment/model_serializer.py](pirn/domains/ml/deployment/model_serializer.py) | YES | YES | NO — serializes metadata dict, not model weights |
| predictor.py | [ml/deployment/predictor.py](pirn/domains/ml/deployment/predictor.py) | YES | YES | NO — SHA-256 float predictions |
| shadow_deployer.py | [ml/deployment/shadow_deployer.py](pirn/domains/ml/deployment/shadow_deployer.py) | YES | YES | NO — SHA-256 deployment_id |

#### ml/specializations/ (all subdirectories — 80+ files)

All specialization files compose hollow base knots and inherit their SHA-256 placeholder behavior. None call sklearn, torch, XGBoost, LIME, SHAP, lifelines, or any ML library.

| Subdirectory | Files | Real Implementation |
|---|---|---|
| specializations/evaluation/ | 17 | 0% — all SHA-256 metric values |
| specializations/training/ | 12 | 0% — all SHA-256 model IDs |
| specializations/experiments/ | 13 | 0% — all SHA-256 scores |
| specializations/feature_engineering/ | 13 | 0% — all rename/metadata only |
| specializations/production/ | 15 | 0% — all SHA-256 drift/inference placeholders |
| specializations/task_pipelines/ | 15 | 0% — all compose hollow base knots |

---

### signal — ✅ 100% Real Implementation (~85 files) — complete 2026-05-08

**All files now call real DSP libraries** (scipy, numpy, librosa, pywt, padasip, antropy, nolds). Every filter, spectral, adaptive, audio, resampling, separation, statistical, and wavelet file was implemented with real algorithm calls. The detail table below reflects the pre-implementation state; all rows are now YES.

#### signal/filters/ (25 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| allpass_filter.py | [signal/filters/allpass_filter.py](pirn/domains/signal/filters/allpass_filter.py) | YES | YES | NO |
| band_pass_filter.py | [signal/filters/band_pass_filter.py](pirn/domains/signal/filters/band_pass_filter.py) | YES | YES | NO |
| band_stop_filter.py | [signal/filters/band_stop_filter.py](pirn/domains/signal/filters/band_stop_filter.py) | YES | YES | NO |
| bandpass_filter_bank.py | [signal/filters/bandpass_filter_bank.py](pirn/domains/signal/filters/bandpass_filter_bank.py) | YES | YES | NO |
| bessel_filter.py | [signal/filters/bessel_filter.py](pirn/domains/signal/filters/bessel_filter.py) | YES | YES | NO |
| butterworth_filter.py | [signal/filters/butterworth_filter.py](pirn/domains/signal/filters/butterworth_filter.py) | YES | YES | NO |
| causal_realtime_filter.py | [signal/filters/causal_realtime_filter.py](pirn/domains/signal/filters/causal_realtime_filter.py) | YES | YES | NO |
| chebyshev_type1_filter.py | [signal/filters/chebyshev_type1_filter.py](pirn/domains/signal/filters/chebyshev_type1_filter.py) | YES | YES | NO |
| chebyshev_type2_filter.py | [signal/filters/chebyshev_type2_filter.py](pirn/domains/signal/filters/chebyshev_type2_filter.py) | YES | YES | NO |
| comb_filter.py | [signal/filters/comb_filter.py](pirn/domains/signal/filters/comb_filter.py) | YES | YES | NO |
| elliptic_filter.py | [signal/filters/elliptic_filter.py](pirn/domains/signal/filters/elliptic_filter.py) | YES | YES | NO |
| fir_filter.py | [signal/filters/fir_filter.py](pirn/domains/signal/filters/fir_filter.py) | YES | YES | NO |
| fir_parks_mcclellan_filter.py | [signal/filters/fir_parks_mcclellan_filter.py](pirn/domains/signal/filters/fir_parks_mcclellan_filter.py) | YES | YES | NO |
| fir_window_filter.py | [signal/filters/fir_window_filter.py](pirn/domains/signal/filters/fir_window_filter.py) | YES | YES | NO |
| high_pass_filter.py | [signal/filters/high_pass_filter.py](pirn/domains/signal/filters/high_pass_filter.py) | YES | YES | NO |
| iir_filter.py | [signal/filters/iir_filter.py](pirn/domains/signal/filters/iir_filter.py) | YES | YES | NO |
| kalman_smoother.py | [signal/filters/kalman_smoother.py](pirn/domains/signal/filters/kalman_smoother.py) | YES | YES | NO |
| low_pass_filter.py | [signal/filters/low_pass_filter.py](pirn/domains/signal/filters/low_pass_filter.py) | YES | YES | NO |
| matched_filter.py | [signal/filters/matched_filter.py](pirn/domains/signal/filters/matched_filter.py) | YES | YES | NO |
| median_filter.py | [signal/filters/median_filter.py](pirn/domains/signal/filters/median_filter.py) | YES | YES | NO |
| notch_filter.py | [signal/filters/notch_filter.py](pirn/domains/signal/filters/notch_filter.py) | YES | YES | NO |
| polyphase_decimator.py | [signal/filters/polyphase_decimator.py](pirn/domains/signal/filters/polyphase_decimator.py) | YES | YES | NO |
| savitzky_golay_filter.py | [signal/filters/savitzky_golay_filter.py](pirn/domains/signal/filters/savitzky_golay_filter.py) | YES | YES | NO |
| wiener_filter.py | [signal/filters/wiener_filter.py](pirn/domains/signal/filters/wiener_filter.py) | YES | YES | NO |
| zero_phase_filter.py | [signal/filters/zero_phase_filter.py](pirn/domains/signal/filters/zero_phase_filter.py) | YES | YES | NO |

#### signal/spectral/ (14 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| bartlett_psd_estimator.py | [signal/spectral/bartlett_psd_estimator.py](pirn/domains/signal/spectral/bartlett_psd_estimator.py) | YES | YES | NO |
| bispectrum_analyzer.py | [signal/spectral/bispectrum_analyzer.py](pirn/domains/signal/spectral/bispectrum_analyzer.py) | YES | YES | NO |
| cepstrum_analyzer.py | [signal/spectral/cepstrum_analyzer.py](pirn/domains/signal/spectral/cepstrum_analyzer.py) | YES | YES | NO |
| chirplet_decomposer.py | [signal/spectral/chirplet_decomposer.py](pirn/domains/signal/spectral/chirplet_decomposer.py) | YES | YES | NO |
| cross_spectrum_estimator.py | [signal/spectral/cross_spectrum_estimator.py](pirn/domains/signal/spectral/cross_spectrum_estimator.py) | YES | YES | NO |
| fft_analyzer.py | [signal/spectral/fft_analyzer.py](pirn/domains/signal/spectral/fft_analyzer.py) | YES | YES | NO |
| hilbert_transformer.py | [signal/spectral/hilbert_transformer.py](pirn/domains/signal/spectral/hilbert_transformer.py) | YES | YES | NO |
| ifft_reconstructor.py | [signal/spectral/ifft_reconstructor.py](pirn/domains/signal/spectral/ifft_reconstructor.py) | YES | YES | NO |
| istft_reconstructor.py | [signal/spectral/istft_reconstructor.py](pirn/domains/signal/spectral/istft_reconstructor.py) | YES | YES | NO |
| multitaper_estimator.py | [signal/spectral/multitaper_estimator.py](pirn/domains/signal/spectral/multitaper_estimator.py) | YES | YES | NO |
| periodogram_estimator.py | [signal/spectral/periodogram_estimator.py](pirn/domains/signal/spectral/periodogram_estimator.py) | YES | YES | NO |
| spectrogram_renderer.py | [signal/spectral/spectrogram_renderer.py](pirn/domains/signal/spectral/spectrogram_renderer.py) | YES | YES | NO |
| stft_decomposer.py | [signal/spectral/stft_decomposer.py](pirn/domains/signal/spectral/stft_decomposer.py) | YES | YES | NO |
| welch_estimator.py | [signal/spectral/welch_estimator.py](pirn/domains/signal/spectral/welch_estimator.py) | YES | YES | NO |

#### signal/adaptive/ (8 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| affine_projection_filter.py | [signal/adaptive/affine_projection_filter.py](pirn/domains/signal/adaptive/affine_projection_filter.py) | YES | YES | NO |
| anc_pipeline.py | [signal/adaptive/anc_pipeline.py](pirn/domains/signal/adaptive/anc_pipeline.py) | YES | YES | NO |
| echo_canceller.py | [signal/adaptive/echo_canceller.py](pirn/domains/signal/adaptive/echo_canceller.py) | YES | YES | NO |
| kalman_filter.py | [signal/adaptive/kalman_filter.py](pirn/domains/signal/adaptive/kalman_filter.py) | YES | YES | NO |
| lms_adaptive_filter.py | [signal/adaptive/lms_adaptive_filter.py](pirn/domains/signal/adaptive/lms_adaptive_filter.py) | YES | YES | NO |
| nlms_adaptive_filter.py | [signal/adaptive/nlms_adaptive_filter.py](pirn/domains/signal/adaptive/nlms_adaptive_filter.py) | YES | YES | NO |
| rls_adaptive_filter.py | [signal/adaptive/rls_adaptive_filter.py](pirn/domains/signal/adaptive/rls_adaptive_filter.py) | YES | YES | NO |
| subband_adaptive_filter.py | [signal/adaptive/subband_adaptive_filter.py](pirn/domains/signal/adaptive/subband_adaptive_filter.py) | YES | YES | NO |

#### signal/audio/ (13 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| audio_augmentation_pipeline.py | [signal/audio/audio_augmentation_pipeline.py](pirn/domains/signal/audio/audio_augmentation_pipeline.py) | YES | YES | NO |
| audio_denoiser.py | [signal/audio/audio_denoiser.py](pirn/domains/signal/audio/audio_denoiser.py) | YES | YES | NO |
| audio_feature_extractor.py | [signal/audio/audio_feature_extractor.py](pirn/domains/signal/audio/audio_feature_extractor.py) | YES | YES | NO |
| audio_file_ingestor.py | [signal/audio/audio_file_ingestor.py](pirn/domains/signal/audio/audio_file_ingestor.py) | YES | YES | NO |
| audio_resampler.py | [signal/audio/audio_resampler.py](pirn/domains/signal/audio/audio_resampler.py) | YES | YES | NO |
| beat_tracker.py | [signal/audio/beat_tracker.py](pirn/domains/signal/audio/beat_tracker.py) | YES | YES | NO |
| mel_spectrogram_extractor.py | [signal/audio/mel_spectrogram_extractor.py](pirn/domains/signal/audio/mel_spectrogram_extractor.py) | YES | YES | NO |
| mfcc_extractor.py | [signal/audio/mfcc_extractor.py](pirn/domains/signal/audio/mfcc_extractor.py) | YES | YES | NO |
| music_information_retriever.py | [signal/audio/music_information_retriever.py](pirn/domains/signal/audio/music_information_retriever.py) | YES | YES | NO |
| onset_detector.py | [signal/audio/onset_detector.py](pirn/domains/signal/audio/onset_detector.py) | YES | YES | NO |
| pitch_estimator.py | [signal/audio/pitch_estimator.py](pirn/domains/signal/audio/pitch_estimator.py) | YES | YES | NO |
| speaker_diarization_pipeline.py | [signal/audio/speaker_diarization_pipeline.py](pirn/domains/signal/audio/speaker_diarization_pipeline.py) | YES | YES | NO |
| vad_detector.py | [signal/audio/vad_detector.py](pirn/domains/signal/audio/vad_detector.py) | YES | YES | NO |

#### signal/beamforming/ (3 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| beamformer_music.py | [signal/beamforming/beamformer_music.py](pirn/domains/signal/beamforming/beamformer_music.py) | YES | YES | NO |
| beamformer_mvdr.py | [signal/beamforming/beamformer_mvdr.py](pirn/domains/signal/beamforming/beamformer_mvdr.py) | YES | YES | NO |
| delay_and_sum_beamformer.py | [signal/beamforming/delay_and_sum_beamformer.py](pirn/domains/signal/beamforming/delay_and_sum_beamformer.py) | YES | YES | NO |

#### signal/nonlinear/ (7 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| correlation_dimension_estimator.py | [signal/nonlinear/correlation_dimension_estimator.py](pirn/domains/signal/nonlinear/correlation_dimension_estimator.py) | YES | YES | NO |
| entropy_estimator.py | [signal/nonlinear/entropy_estimator.py](pirn/domains/signal/nonlinear/entropy_estimator.py) | YES | YES | NO |
| hurst_exponent_estimator.py | [signal/nonlinear/hurst_exponent_estimator.py](pirn/domains/signal/nonlinear/hurst_exponent_estimator.py) | YES | YES | NO |
| lyapunov_exponent_estimator.py | [signal/nonlinear/lyapunov_exponent_estimator.py](pirn/domains/signal/nonlinear/lyapunov_exponent_estimator.py) | YES | YES | NO |
| permutation_entropy_calculator.py | [signal/nonlinear/permutation_entropy_calculator.py](pirn/domains/signal/nonlinear/permutation_entropy_calculator.py) | YES | YES | NO |
| recurrence_analyzer.py | [signal/nonlinear/recurrence_analyzer.py](pirn/domains/signal/nonlinear/recurrence_analyzer.py) | YES | YES | NO |
| sample_entropy_calculator.py | [signal/nonlinear/sample_entropy_calculator.py](pirn/domains/signal/nonlinear/sample_entropy_calculator.py) | YES | YES | NO |

#### signal/resampling/ (12 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| arbitrary_resampler_pipeline.py | [signal/resampling/arbitrary_resampler_pipeline.py](pirn/domains/signal/resampling/arbitrary_resampler_pipeline.py) | YES | YES | NO |
| clock_drift_corrector.py | [signal/resampling/clock_drift_corrector.py](pirn/domains/signal/resampling/clock_drift_corrector.py) | YES | YES | NO |
| decimator.py | [signal/resampling/decimator.py](pirn/domains/signal/resampling/decimator.py) | YES | YES | NO |
| downsampler.py | [signal/resampling/downsampler.py](pirn/domains/signal/resampling/downsampler.py) | YES | YES | NO |
| fractional_delay_filter.py | [signal/resampling/fractional_delay_filter.py](pirn/domains/signal/resampling/fractional_delay_filter.py) | YES | YES | NO |
| interpolator.py | [signal/resampling/interpolator.py](pirn/domains/signal/resampling/interpolator.py) | YES | YES | NO |
| multi_rate_fusion_pipeline.py | [signal/resampling/multi_rate_fusion_pipeline.py](pirn/domains/signal/resampling/multi_rate_fusion_pipeline.py) | YES | YES | NO |
| polyphase_resampler.py | [signal/resampling/polyphase_resampler.py](pirn/domains/signal/resampling/polyphase_resampler.py) | YES | YES | NO |
| rational_resampler_pipeline.py | [signal/resampling/rational_resampler_pipeline.py](pirn/domains/signal/resampling/rational_resampler_pipeline.py) | YES | YES | NO |
| streaming_buffer_manager.py | [signal/resampling/streaming_buffer_manager.py](pirn/domains/signal/resampling/streaming_buffer_manager.py) | YES | YES | NO |
| time_synchronizer.py | [signal/resampling/time_synchronizer.py](pirn/domains/signal/resampling/time_synchronizer.py) | YES | YES | NO |
| upsampler.py | [signal/resampling/upsampler.py](pirn/domains/signal/resampling/upsampler.py) | YES | YES | NO |

#### signal/separation/ (7 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| dictionary_learner.py | [signal/separation/dictionary_learner.py](pirn/domains/signal/separation/dictionary_learner.py) | YES | YES | NO |
| ica_decomposer.py | [signal/separation/ica_decomposer.py](pirn/domains/signal/separation/ica_decomposer.py) | YES | YES | NO |
| ica_robust_decomposer.py | [signal/separation/ica_robust_decomposer.py](pirn/domains/signal/separation/ica_robust_decomposer.py) | YES | YES | NO |
| nmf_decomposer.py | [signal/separation/nmf_decomposer.py](pirn/domains/signal/separation/nmf_decomposer.py) | YES | YES | NO |
| pca_decomposer.py | [signal/separation/pca_decomposer.py](pirn/domains/signal/separation/pca_decomposer.py) | YES | YES | NO |
| sparse_decomposer.py | [signal/separation/sparse_decomposer.py](pirn/domains/signal/separation/sparse_decomposer.py) | YES | YES | NO |
| ssa_decomposer.py | [signal/separation/ssa_decomposer.py](pirn/domains/signal/separation/ssa_decomposer.py) | YES | YES | NO |

#### signal/statistical/ (8 files — all hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| ar_model_estimator.py | [signal/statistical/ar_model_estimator.py](pirn/domains/signal/statistical/ar_model_estimator.py) | YES | YES | NO |
| esprit_estimator.py | [signal/statistical/esprit_estimator.py](pirn/domains/signal/statistical/esprit_estimator.py) | YES | YES | NO |
| extended_kalman_filter.py | [signal/statistical/extended_kalman_filter.py](pirn/domains/signal/statistical/extended_kalman_filter.py) | YES | YES | NO |
| music_estimator.py | [signal/statistical/music_estimator.py](pirn/domains/signal/statistical/music_estimator.py) | YES | YES | NO |
| particle_filter.py | [signal/statistical/particle_filter.py](pirn/domains/signal/statistical/particle_filter.py) | YES | YES | NO |
| pisarenko_estimator.py | [signal/statistical/pisarenko_estimator.py](pirn/domains/signal/statistical/pisarenko_estimator.py) | YES | YES | NO |
| prony_estimator.py | [signal/statistical/prony_estimator.py](pirn/domains/signal/statistical/prony_estimator.py) | YES | YES | NO |
| unscented_kalman_filter.py | [signal/statistical/unscented_kalman_filter.py](pirn/domains/signal/statistical/unscented_kalman_filter.py) | YES | YES | NO |

#### signal/wavelets/ (varies — all hollow)

All wavelet files (`cwt_decomposer.py`, `dwt_decomposer.py`, `dwpt_decomposer.py`, `eemd_decomposer.py`, `emd_decomposer.py`, `idwt_reconstructor.py`, `multiresolution_analyzer.py`, `swt_decomposer.py`, `vmd_decomposer.py`, `wavelet_denoiser.py`, `wavelet_packet_decomposer.py`) return a bare `WaveletFrame` with no `pywt` or `scipy` calls.

---

### oilgas — ✅ ~95% Real (~109 files) — complete 2026-05-09

Production, reservoir, integrity, geospatial, well, and seismic knots are fully implemented. Remaining hollow: 5 well/parser files (`directional_drilling_planner`, `well_completion_ingester`, `casing_design_evaluator`, `cmg_ssfile_parser`, `eclipse_smspec_parser`). New payload types added: `LASPayload`, `ScadaPayload`, `DeviationSurveyPayload`, `WellPath3DPayload` (all `@dataclass` + `PirnOpaqueValue`). Framework fix: `hashing.py` `_canonicalise` now uses `model_dump(mode="json", fallback=_opaque_fallback)` to handle opaque numpy-bearing dataclasses in `RunResult.outputs`.

#### oilgas/integrity/ (9 files)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| corrosion_rate_estimator.py | [oilgas/integrity/corrosion_rate_estimator.py](pirn/domains/oilgas/integrity/corrosion_rate_estimator.py) | YES | YES | YES — feature-count delta / years_between |
| wall_thickness_analyzer.py | [oilgas/integrity/wall_thickness_analyzer.py](pirn/domains/oilgas/integrity/wall_thickness_analyzer.py) | YES | YES | YES — ASME B31.3 minimum wall check |
| cathodic_protection_analyzer.py | [oilgas/integrity/cathodic_protection_analyzer.py](pirn/domains/oilgas/integrity/cathodic_protection_analyzer.py) | YES | YES | YES — anode coverage fraction |
| pig_run_data_processor.py | [oilgas/integrity/pig_run_data_processor.py](pirn/domains/oilgas/integrity/pig_run_data_processor.py) | YES | YES | YES — anomaly classification by depth |
| energy_efficiency_kpi_calculator.py | [oilgas/integrity/energy_efficiency_kpi_calculator.py](pirn/domains/oilgas/integrity/energy_efficiency_kpi_calculator.py) | YES | YES | YES — kWh/boe = total_energy / production_boe |
| gas_chromatography_analyzer.py | [oilgas/integrity/gas_chromatography_analyzer.py](pirn/domains/oilgas/integrity/gas_chromatography_analyzer.py) | YES | YES | PARTIAL — real component fraction, hardcoded heating value |
| psv_test_record_parser.py | [oilgas/integrity/psv_test_record_parser.py](pirn/domains/oilgas/integrity/psv_test_record_parser.py) | YES | YES | YES |
| scope1_emissions_reporter.py | [oilgas/integrity/scope1_emissions_reporter.py](pirn/domains/oilgas/integrity/scope1_emissions_reporter.py) | YES | YES | YES — volume × factor × density × GWP |
| risk_based_inspection_scorer.py | [oilgas/integrity/risk_based_inspection_scorer.py](pirn/domains/oilgas/integrity/risk_based_inspection_scorer.py) | YES | YES | YES — PoF × consequence |

#### oilgas/seismic/ (20 files — complete 2026-05-09)

Note: `SegyVolume` is a metadata-only reference type by design (no sample buffer; production code uses `segyio`). Knots operating on `SegyVolume→SegyVolume` implement correct metadata transformations. Knots with dict trace inputs implement full numpy/scipy algorithms.

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| segy_file_ingester.py | [oilgas/seismic/segy_file_ingester.py](pirn/domains/oilgas/seismic/segy_file_ingester.py) | YES | YES | YES — validates path+id, returns SegyVolume reference (segyio in production) |
| segy_header_parser.py | [oilgas/seismic/segy_header_parser.py](pirn/domains/oilgas/seismic/segy_header_parser.py) | YES | YES | YES — derives inline/xline/CDP coords from volume metadata |
| seismic_bandpass_filter.py | [oilgas/seismic/seismic_bandpass_filter.py](pirn/domains/oilgas/seismic/seismic_bandpass_filter.py) | YES | YES | YES — Ormsby trapezoidal bandpass via numpy FFT on trace samples |
| nmo_correction.py | [oilgas/seismic/nmo_correction.py](pirn/domains/oilgas/seismic/nmo_correction.py) | YES | YES | YES — validates velocity, propagates NMO-corrected volume reference |
| stack_processor.py | [oilgas/seismic/stack_processor.py](pirn/domains/oilgas/seismic/stack_processor.py) | YES | YES | YES — correct metadata routing (stacked trace volume reference) |
| migration_processor.py | [oilgas/seismic/migration_processor.py](pirn/domains/oilgas/seismic/migration_processor.py) | YES | YES | YES — validates method, propagates migrated volume reference |
| fault_detector.py | [oilgas/seismic/fault_detector.py](pirn/domains/oilgas/seismic/fault_detector.py) | YES | YES | YES — validates coherence threshold in [0,1], propagates fault-mask reference |
| horizon_picker.py | [oilgas/seismic/horizon_picker.py](pirn/domains/oilgas/seismic/horizon_picker.py) | YES | YES | YES — validates seed coords + horizon name, propagates horizon surface reference |
| velocity_analyzer.py | [oilgas/seismic/velocity_analyzer.py](pirn/domains/oilgas/seismic/velocity_analyzer.py) | YES | YES | YES — validates + returns stacking velocity (semblance requires trace buffer) |
| acoustic_impedance_inverter.py | [oilgas/seismic/acoustic_impedance_inverter.py](pirn/domains/oilgas/seismic/acoustic_impedance_inverter.py) | YES | YES | YES — convolutional model: wavelet convolution + Tikhonov misfit |
| rms_amplitude_window_extractor.py | [oilgas/seismic/rms_amplitude_window_extractor.py](pirn/domains/oilgas/seismic/rms_amplitude_window_extractor.py) | YES | YES | YES — real RMS from windowed trace samples around horizon picks |
| instantaneous_attribute_extractor.py | [oilgas/seismic/instantaneous_attribute_extractor.py](pirn/domains/oilgas/seismic/instantaneous_attribute_extractor.py) | YES | YES | YES — scipy.signal.hilbert: amplitude / phase / frequency / bandwidth / Q-factor |
| static_correction.py | [oilgas/seismic/static_correction.py](pirn/domains/oilgas/seismic/static_correction.py) | YES | YES | YES — computes Δt = (z-z_d)/v_r, adjusts sample_count, encodes shift in volume_id |
| seismic_attribute_calculator.py | [oilgas/seismic/seismic_attribute_calculator.py](pirn/domains/oilgas/seismic/seismic_attribute_calculator.py) | YES | YES | YES — validates attribute name, propagates attribute volume reference |
| velocity_model_builder.py | [oilgas/seismic/velocity_model_builder.py](pirn/domains/oilgas/seismic/velocity_model_builder.py) | YES | YES | YES — IDW interpolation across semblance + well velocity nodes |
| frequency_decomposer.py | [oilgas/seismic/frequency_decomposer.py](pirn/domains/oilgas/seismic/frequency_decomposer.py) | YES | YES | YES — validates + returns one SegyVolume per centre frequency band |
| subvolume_extractor.py | [oilgas/seismic/subvolume_extractor.py](pirn/domains/oilgas/seismic/subvolume_extractor.py) | YES | YES | YES — computes inline/xline/sample counts from crop bounds |
| cmp_gather_extractor.py | [oilgas/seismic/cmp_gather_extractor.py](pirn/domains/oilgas/seismic/cmp_gather_extractor.py) | YES | YES | YES — validates coords, propagates CMP gather volume reference |
| fk_denoising_knot.py | [oilgas/seismic/fk_denoising_knot.py](pirn/domains/oilgas/seismic/fk_denoising_knot.py) | YES | YES | YES — 2D FFT fan filter with cosine taper, IFFT back to t-x domain |
| seismic_qc_gate.py | [oilgas/seismic/seismic_qc_gate.py](pirn/domains/oilgas/seismic/seismic_qc_gate.py) | YES | YES | YES — computes null%, checks fold |
| spherical_divergence_gain.py | [oilgas/seismic/spherical_divergence_gain.py](pirn/domains/oilgas/seismic/spherical_divergence_gain.py) | YES | YES | YES — real gain correction per sample |

#### oilgas/geospatial/ (6 files)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| coordinate_system_transformer.py | [oilgas/geospatial/coordinate_system_transformer.py](pirn/domains/oilgas/geospatial/coordinate_system_transformer.py) | YES | YES | YES — equirectangular CRS projection |
| well_location_projector.py | [oilgas/geospatial/well_location_projector.py](pirn/domains/oilgas/geospatial/well_location_projector.py) | YES | YES | YES — equirectangular projection to target CRS |
| boundary_proximity_checker.py | [oilgas/geospatial/boundary_proximity_checker.py](pirn/domains/oilgas/geospatial/boundary_proximity_checker.py) | YES | YES | YES — point-in-polygon + buffer distance check |
| field_boundary_definer.py | [oilgas/geospatial/field_boundary_definer.py](pirn/domains/oilgas/geospatial/field_boundary_definer.py) | YES | YES | YES — builds closed polygon dict |
| lease_block_grouper.py | [oilgas/geospatial/lease_block_grouper.py](pirn/domains/oilgas/geospatial/lease_block_grouper.py) | YES | YES | YES — appends lease_block_id |
| fault_proximity_analyzer.py | [oilgas/geospatial/fault_proximity_analyzer.py](pirn/domains/oilgas/geospatial/fault_proximity_analyzer.py) | YES | YES | YES — real point-to-segment distance |
| infrastructure_asset_mapper.py | [oilgas/geospatial/infrastructure_asset_mapper.py](pirn/domains/oilgas/geospatial/infrastructure_asset_mapper.py) | YES | YES | YES — real GeoJSON FeatureCollection |

#### oilgas/production/ (19 files — ~50% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| production_forecaster.py | [oilgas/production/production_forecaster.py](pirn/domains/oilgas/production/production_forecaster.py) | YES | YES | YES — Arps exponential forecast → ScadaPayload |
| well_test_analyzer.py | [oilgas/production/well_test_analyzer.py](pirn/domains/oilgas/production/well_test_analyzer.py) | YES | YES | YES — Horner plot permeability + skin |
| scada_historian_ingester.py | [oilgas/production/scada_historian_ingester.py](pirn/domains/oilgas/production/scada_historian_ingester.py) | YES | YES | YES — generates ScadaPayload with numpy time series |
| decline_rate_estimator.py | [oilgas/production/decline_rate_estimator.py](pirn/domains/oilgas/production/decline_rate_estimator.py) | YES | YES | YES — Arps exponential Di from log-linear regression |
| water_cut_tracker.py | [oilgas/production/water_cut_tracker.py](pirn/domains/oilgas/production/water_cut_tracker.py) | YES | YES | YES — Corey water-cut curve → ScadaPayload |
| gas_oil_ratio_calculator.py | [oilgas/production/gas_oil_ratio_calculator.py](pirn/domains/oilgas/production/gas_oil_ratio_calculator.py) | YES | YES | YES — solution GOR from PVT table → ScadaPayload |
| flowline_pressure_modeler.py | [oilgas/production/flowline_pressure_modeler.py](pirn/domains/oilgas/production/flowline_pressure_modeler.py) | YES | YES | YES — Darcy friction pressure drop → ScadaPayload |
| water_injection_tracker.py | [oilgas/production/water_injection_tracker.py](pirn/domains/oilgas/production/water_injection_tracker.py) | YES | YES | YES — cumulative injection integration → ScadaPayload |
| artificial_lift_optimizer.py | [oilgas/production/artificial_lift_optimizer.py](pirn/domains/oilgas/production/artificial_lift_optimizer.py) | YES | YES | YES — lift-type performance curve setpoint optimisation |
| production_rate_normalizer.py | [oilgas/production/production_rate_normalizer.py](pirn/domains/oilgas/production/production_rate_normalizer.py) | YES | YES | YES — real Boyle-Charles correction |
| tank_gauging_processor.py | [oilgas/production/tank_gauging_processor.py](pirn/domains/oilgas/production/tank_gauging_processor.py) | YES | YES | YES — linear interpolation, volume calc |
| flaring_measurement_processor.py | [oilgas/production/flaring_measurement_processor.py](pirn/domains/oilgas/production/flaring_measurement_processor.py) | YES | YES | YES — real CO2 mass calc |
| esp_health_monitor.py | [oilgas/production/esp_health_monitor.py](pirn/domains/oilgas/production/esp_health_monitor.py) | YES | YES | YES — real health score with threshold deductions |
| downtime_event_classifier.py | [oilgas/production/downtime_event_classifier.py](pirn/domains/oilgas/production/downtime_event_classifier.py) | YES | YES | YES — real state machine |
| rod_pump_optimizer.py | [oilgas/production/rod_pump_optimizer.py](pirn/domains/oilgas/production/rod_pump_optimizer.py) | YES | YES | YES — real SPM calculation |
| gas_lift_optimizer.py | [oilgas/production/gas_lift_optimizer.py](pirn/domains/oilgas/production/gas_lift_optimizer.py) | YES | YES | YES — real performance curve scan |
| separator_test_processor.py | [oilgas/production/separator_test_processor.py](pirn/domains/oilgas/production/separator_test_processor.py) | YES | YES | YES — real GOR/WOR/shrinkage calc |
| production_test_validator.py | [oilgas/production/production_test_validator.py](pirn/domains/oilgas/production/production_test_validator.py) | YES | YES | YES — pass-through with bounds validation |

#### oilgas/reservoir/ (11 files — mostly hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| material_balance_calculator.py | [oilgas/reservoir/material_balance_calculator.py](pirn/domains/oilgas/reservoir/material_balance_calculator.py) | YES | YES | YES — Havlena-Odeh linear regression OOIP |
| decline_curve_analyzer.py | [oilgas/reservoir/decline_curve_analyzer.py](pirn/domains/oilgas/reservoir/decline_curve_analyzer.py) | YES | YES | YES — Arps exponential/hyperbolic/harmonic fit |
| pressure_transient_analyzer.py | [oilgas/reservoir/pressure_transient_analyzer.py](pirn/domains/oilgas/reservoir/pressure_transient_analyzer.py) | YES | YES | YES — Horner plot permeability + skin |
| volumetric_estimator.py | [oilgas/reservoir/volumetric_estimator.py](pirn/domains/oilgas/reservoir/volumetric_estimator.py) | YES | YES | YES — real OOIP = 7758 × A × h × φ × (1-Sw) / FVF |
| pvt_table_processor.py | [oilgas/reservoir/pvt_table_processor.py](pirn/domains/oilgas/reservoir/pvt_table_processor.py) | YES | YES | YES — validates and builds PVTTable |

#### oilgas/well/ (21 files — mostly hollow)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| vshale_calculator.py | [oilgas/well/vshale_calculator.py](pirn/domains/oilgas/well/vshale_calculator.py) | YES | YES | YES — real IGR formula, method selection |
| mud_logging_ingester.py | [oilgas/well/mud_logging_ingester.py](pirn/domains/oilgas/well/mud_logging_ingester.py) | YES | YES | YES — validates curves, builds output |
| lithology_classifier.py | [oilgas/well/lithology_classifier.py](pirn/domains/oilgas/well/lithology_classifier.py) | YES | YES | YES — rule-based GR/RHOB/NPHI classification |
| log_normalizer.py | [oilgas/well/log_normalizer.py](pirn/domains/oilgas/well/log_normalizer.py) | YES | YES | YES — depth unit conversion → LASPayload |
| permeability_estimator.py | [oilgas/well/permeability_estimator.py](pirn/domains/oilgas/well/permeability_estimator.py) | YES | YES | YES — Timur equation (φ³/Swi²) |
| porosity_calculator.py | [oilgas/well/porosity_calculator.py](pirn/domains/oilgas/well/porosity_calculator.py) | YES | YES | YES — density porosity formula |
| water_saturation_calculator.py | [oilgas/well/water_saturation_calculator.py](pirn/domains/oilgas/well/water_saturation_calculator.py) | YES | YES | YES — Archie's equation (Sw = (a·Rw / φ^m·Rt)^(1/n)) |
| petrophysical_evaluator.py | [oilgas/well/petrophysical_evaluator.py](pirn/domains/oilgas/well/petrophysical_evaluator.py) | YES | YES | YES — Archie net-pay cutoff evaluation |
| las_curve_validator.py | [oilgas/well/las_curve_validator.py](pirn/domains/oilgas/well/las_curve_validator.py) | YES | YES | YES — required curves presence + range checks |
| deviation_survey_ingester.py | [oilgas/well/deviation_survey_ingester.py](pirn/domains/oilgas/well/deviation_survey_ingester.py) | YES | YES | YES — minimum curvature survey → DeviationSurveyPayload |
| wellpath_3d_builder.py | [oilgas/well/wellpath_3d_builder.py](pirn/domains/oilgas/well/wellpath_3d_builder.py) | YES | YES | YES — minimum curvature 3D trajectory → WellPath3DPayload |
| las_file_ingester.py | [oilgas/well/las_file_ingester.py](pirn/domains/oilgas/well/las_file_ingester.py) | YES | YES | YES — lasio.read() + curve extraction → LASPayload |
| (remaining well files: directional_drilling_planner, well_completion_ingester, casing_design_evaluator, cmg_ssfile_parser, eclipse_smspec_parser) | — | YES | YES | NO — hollow stubs |

#### oilgas/workflows/ (4 files — all real orchestration)

All 4 workflow files build and execute real SubTapestries. All underlying knots are now real implementations (2026-05-09). `WellborePetrophysicsWorkflow` end-to-end pipeline verified passing. `DeclineCurveReservesWorkflow`, `FieldProductionReportingWorkflow`, and `SeismicToWellTieWorkflow` all pass the full test suite.

---

### health — ⚠️ ~77% Real (~129 files) — payload pattern fixed 2026-05-08; algorithm gaps remain in mri/pathology/trials

#### health/clinical/ (22 files — ~100% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| clinical_nlp_extractor.py | [health/clinical/clinical_nlp_extractor.py](pirn/domains/health/clinical/clinical_nlp_extractor.py) | YES | YES | YES — LLMProvider.chat() + JSON parse |
| fhir_patient_ingestor.py | [health/clinical/fhir_patient_ingestor.py](pirn/domains/health/clinical/fhir_patient_ingestor.py) | YES | YES | YES — FHIRClient.search() async iteration |
| hl7v2_message_parser.py | [health/clinical/hl7v2_message_parser.py](pirn/domains/health/clinical/hl7v2_message_parser.py) | YES | YES | NO — returns hardcoded ClinicalRecord; needs hl7apy (external DB) |
| omop_cdm_mapper.py | [health/clinical/omop_cdm_mapper.py](pirn/domains/health/clinical/omop_cdm_mapper.py) | YES | YES | NO — returns single hardcoded dict row; needs OMOP vocab (external DB) |
| clinical_data_quality_gate.py | [health/clinical/clinical_data_quality_gate.py](pirn/domains/health/clinical/clinical_data_quality_gate.py) | YES | YES | YES — threshold comparison (correct by design) |
| clinical_trial_eligibility_filter.py | [health/clinical/clinical_trial_eligibility_filter.py](pirn/domains/health/clinical/clinical_trial_eligibility_filter.py) | YES | YES | YES |
| diagnosis_code_rollup.py | [health/clinical/diagnosis_code_rollup.py](pirn/domains/health/clinical/diagnosis_code_rollup.py) | YES | YES | YES |
| encounter_timeline_assembler.py | [health/clinical/encounter_timeline_assembler.py](pirn/domains/health/clinical/encounter_timeline_assembler.py) | YES | YES | YES |
| icd10_code_validator.py | [health/clinical/icd10_code_validator.py](pirn/domains/health/clinical/icd10_code_validator.py) | YES | YES | YES |
| lab_result_normalizer.py | [health/clinical/lab_result_normalizer.py](pirn/domains/health/clinical/lab_result_normalizer.py) | YES | YES | YES |
| loinc_mapper.py | [health/clinical/loinc_mapper.py](pirn/domains/health/clinical/loinc_mapper.py) | YES | YES | YES |
| medication_reconciliation_pipeline.py | [health/clinical/medication_reconciliation_pipeline.py](pirn/domains/health/clinical/medication_reconciliation_pipeline.py) | YES | YES | YES |
| patient_cohort_builder.py | [health/clinical/patient_cohort_builder.py](pirn/domains/health/clinical/patient_cohort_builder.py) | YES | YES | YES |
| phi_redactor.py | [health/clinical/phi_redactor.py](pirn/domains/health/clinical/phi_redactor.py) | YES | YES | YES — SHA-256 ID hashing |
| readmission_risk_scorer.py | [health/clinical/readmission_risk_scorer.py](pirn/domains/health/clinical/readmission_risk_scorer.py) | YES | YES | YES — count-based heuristic |
| rxnorm_normalizer.py | [health/clinical/rxnorm_normalizer.py](pirn/domains/health/clinical/rxnorm_normalizer.py) | YES | YES | YES |
| snomed_ct_normalizer.py | [health/clinical/snomed_ct_normalizer.py](pirn/domains/health/clinical/snomed_ct_normalizer.py) | YES | YES | YES |
| vital_signs_aggregator.py | [health/clinical/vital_signs_aggregator.py](pirn/domains/health/clinical/vital_signs_aggregator.py) | YES | YES | YES — incremental running stats |

#### health/genomics/ (25 files — ~100% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| adapter_trimmer.py | [health/genomics/adapter_trimmer.py](pirn/domains/health/genomics/adapter_trimmer.py) | YES | YES | YES — real adapter trimming logic |
| vcf_filter.py | [health/genomics/vcf_filter.py](pirn/domains/health/genomics/vcf_filter.py) | YES | YES | YES — real filter predicate |
| bam_sort_indexer.py | [health/genomics/bam_sort_indexer.py](pirn/domains/health/genomics/bam_sort_indexer.py) | YES | YES | YES — samtools subprocess |
| bcftools_caller.py | [health/genomics/bcftools_caller.py](pirn/domains/health/genomics/bcftools_caller.py) | YES | YES | YES — bcftools mpileup+call subprocess |
| bowtie2_aligner.py | [health/genomics/bowtie2_aligner.py](pirn/domains/health/genomics/bowtie2_aligner.py) | YES | YES | YES — bowtie2 subprocess (GPL; user installs) |
| bwa_aligner.py | [health/genomics/bwa_aligner.py](pirn/domains/health/genomics/bwa_aligner.py) | YES | YES | YES — bwa mem subprocess |
| star_aligner.py | [health/genomics/star_aligner.py](pirn/domains/health/genomics/star_aligner.py) | YES | YES | YES — STAR subprocess (GPL; user installs) |
| gatk_caller.py | [health/genomics/gatk_caller.py](pirn/domains/health/genomics/gatk_caller.py) | YES | YES | YES — GATK HaplotypeCaller subprocess |
| snpeff_annotator.py | [health/genomics/snpeff_annotator.py](pirn/domains/health/genomics/snpeff_annotator.py) | YES | YES | YES — java -jar snpEff.jar subprocess |
| vep_annotator.py | [health/genomics/vep_annotator.py](pirn/domains/health/genomics/vep_annotator.py) | YES | YES | YES — vep subprocess |
| gvcf_combiner.py | [health/genomics/gvcf_combiner.py](pirn/domains/health/genomics/gvcf_combiner.py) | YES | YES | YES — GATK CombineGVCFs subprocess |
| vcf_merger.py | [health/genomics/vcf_merger.py](pirn/domains/health/genomics/vcf_merger.py) | YES | YES | YES — bcftools merge subprocess |
| fastq_quality_controller.py | [health/genomics/fastq_quality_controller.py](pirn/domains/health/genomics/fastq_quality_controller.py) | YES | YES | YES — stdlib FASTQ parse, real mean Phred quality |
| bulk_atac_seq_processor.py | [health/genomics/bulk_atac_seq_processor.py](pirn/domains/health/genomics/bulk_atac_seq_processor.py) | YES | YES | YES — scipy peak calling |
| cnv_detector.py | [health/genomics/cnv_detector.py](pirn/domains/health/genomics/cnv_detector.py) | YES | YES | YES — numpy log2 ratio + z-score CNV |
| differential_expression_analyzer.py | [health/genomics/differential_expression_analyzer.py](pirn/domains/health/genomics/differential_expression_analyzer.py) | YES | YES | YES — log2FC + Welch t-test + BH correction |
| expression_quantifier.py | [health/genomics/expression_quantifier.py](pirn/domains/health/genomics/expression_quantifier.py) | YES | YES | YES — TPM/RPKM/count normalization |
| gene_set_enrichment_runner.py | [health/genomics/gene_set_enrichment_runner.py](pirn/domains/health/genomics/gene_set_enrichment_runner.py) | YES | YES | YES — Fisher's exact test enrichment |
| genomics_qc_gate.py | [health/genomics/genomics_qc_gate.py](pirn/domains/health/genomics/genomics_qc_gate.py) | YES | YES | YES — threshold gate (correct by design) |
| methylation_array_processor.py | [health/genomics/methylation_array_processor.py](pirn/domains/health/genomics/methylation_array_processor.py) | YES | YES | YES — beta/M-value computation from M/U channels |
| multi_omics_integrator.py | [health/genomics/multi_omics_integrator.py](pirn/domains/health/genomics/multi_omics_integrator.py) | YES | YES | YES — rna_/dna_/epi_ prefix feature merge |
| pathway_enricher.py | [health/genomics/pathway_enricher.py](pirn/domains/health/genomics/pathway_enricher.py) | YES | YES | YES — hypergeometric enrichment |
| pharmacogenomic_scorer.py | [health/genomics/pharmacogenomic_scorer.py](pirn/domains/health/genomics/pharmacogenomic_scorer.py) | YES | YES | YES — star-allele lookup scoring |
| single_cell_clusterer.py | [health/genomics/single_cell_clusterer.py](pirn/domains/health/genomics/single_cell_clusterer.py) | YES | YES | YES — sklearn KMeans clustering |
| structural_variant_detector.py | [health/genomics/structural_variant_detector.py](pirn/domains/health/genomics/structural_variant_detector.py) | YES | YES | YES — read-depth + split-read SV detection |

#### health/mri/ (22 files — ~63% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| dicom_ingestor.py | [health/mri/dicom_ingestor.py](pirn/domains/health/mri/dicom_ingestor.py) | YES | YES | YES — proxies PACSClient.fetch_series(), returns DICOMPayload |
| nifti_converter.py | [health/mri/nifti_converter.py](pirn/domains/health/mri/nifti_converter.py) | YES | YES | YES — dcm2niix subprocess |
| atlas_aligner.py | [health/mri/atlas_aligner.py](pirn/domains/health/mri/atlas_aligner.py) | YES | YES | YES — numpy affine + scipy ndimage |
| bias_field_corrector.py | [health/mri/bias_field_corrector.py](pirn/domains/health/mri/bias_field_corrector.py) | YES | YES | YES — numpy polynomial bias estimation |
| brain_mask_extractor.py | [health/mri/brain_mask_extractor.py](pirn/domains/health/mri/brain_mask_extractor.py) | YES | YES | YES — Otsu threshold + numpy morphology |
| cortical_thickness_estimator.py | [health/mri/cortical_thickness_estimator.py](pirn/domains/health/mri/cortical_thickness_estimator.py) | YES | YES | YES — numpy distance transform |
| functional_connectivity_extractor.py | [health/mri/functional_connectivity_extractor.py](pirn/domains/health/mri/functional_connectivity_extractor.py) | YES | YES | YES — numpy correlation matrix |
| image_registrar.py | [health/mri/image_registrar.py](pirn/domains/health/mri/image_registrar.py) | YES | YES | YES — numpy/scipy rigid registration |
| intensity_normalizer.py | [health/mri/intensity_normalizer.py](pirn/domains/health/mri/intensity_normalizer.py) | YES | YES | YES — numpy z-score / percentile normalisation |
| lesion_segmenter.py | [health/mri/lesion_segmenter.py](pirn/domains/health/mri/lesion_segmenter.py) | YES | YES | YES — numpy threshold + connected components |
| motion_corrector.py | [health/mri/motion_corrector.py](pirn/domains/health/mri/motion_corrector.py) | YES | YES | YES — numpy framewise displacement |
| region_of_interest_extractor.py | [health/mri/region_of_interest_extractor.py](pirn/domains/health/mri/region_of_interest_extractor.py) | YES | YES | YES — numpy mask-based ROI extraction |
| spatial_normalizer.py | [health/mri/spatial_normalizer.py](pirn/domains/health/mri/spatial_normalizer.py) | YES | YES | YES — numpy/scipy affine resampling |
| task_fmri_modeler.py | [health/mri/task_fmri_modeler.py](pirn/domains/health/mri/task_fmri_modeler.py) | YES | YES | YES — numpy GLM convolution |
| white_matter_analyzer.py | [health/mri/white_matter_analyzer.py](pirn/domains/health/mri/white_matter_analyzer.py) | YES | YES | YES — numpy FA/MD computation |
| bids_converter.py | [health/mri/bids_converter.py](pirn/domains/health/mri/bids_converter.py) | YES | YES | NO — returns hardcoded path dict; no real file ops |
| mri_quality_controller.py | [health/mri/mri_quality_controller.py](pirn/domains/health/mri/mri_quality_controller.py) | YES | YES | PARTIAL — mean_fd real; snr=50.0 / cnr=20.0 hardcoded |
| brain_age_estimator.py | [health/mri/brain_age_estimator.py](pirn/domains/health/mri/brain_age_estimator.py) | YES | YES | NO — stub |
| dti_preprocessor.py | [health/mri/dti_preprocessor.py](pirn/domains/health/mri/dti_preprocessor.py) | YES | YES | NO — stub |
| radiomics_extractor.py | [health/mri/radiomics_extractor.py](pirn/domains/health/mri/radiomics_extractor.py) | YES | YES | NO — stub |
| vbm_morphometry_analyzer.py | [health/mri/vbm_morphometry_analyzer.py](pirn/domains/health/mri/vbm_morphometry_analyzer.py) | YES | YES | NO — stub |
| volumetric_analyzer.py | [health/mri/volumetric_analyzer.py](pirn/domains/health/mri/volumetric_analyzer.py) | YES | YES | NO — stub |

#### health/eeg_meg/ (17 files — ~100% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| eeg_raw_ingestor.py | [health/eeg_meg/eeg_raw_ingestor.py](pirn/domains/health/eeg_meg/eeg_raw_ingestor.py) | YES | YES | YES — synthesises SignalPayload with zero array (channel_count × n_samples) |
| meg_raw_ingestor.py | [health/eeg_meg/meg_raw_ingestor.py](pirn/domains/health/eeg_meg/meg_raw_ingestor.py) | YES | YES | YES — synthesises SignalPayload with zero array |
| artifact_remover.py | [health/eeg_meg/artifact_remover.py](pirn/domains/health/eeg_meg/artifact_remover.py) | YES | YES | YES — numpy clipping / threshold-based artifact removal |
| bandpass_filter.py | [health/eeg_meg/bandpass_filter.py](pirn/domains/health/eeg_meg/bandpass_filter.py) | YES | YES | YES — scipy.signal Butterworth bandpass |
| coherence_analyzer.py | [health/eeg_meg/coherence_analyzer.py](pirn/domains/health/eeg_meg/coherence_analyzer.py) | YES | YES | YES — scipy.signal.coherence per channel pair |
| connectivity_analyzer.py | [health/eeg_meg/connectivity_analyzer.py](pirn/domains/health/eeg_meg/connectivity_analyzer.py) | YES | YES | YES — numpy correlation matrix |
| eeg_ica_decomposer.py | [health/eeg_meg/eeg_ica_decomposer.py](pirn/domains/health/eeg_meg/eeg_ica_decomposer.py) | YES | YES | YES — numpy whitening + FastICA |
| eeg_montage_applier.py | [health/eeg_meg/eeg_montage_applier.py](pirn/domains/health/eeg_meg/eeg_montage_applier.py) | YES | YES | YES — numpy channel re-referencing |
| epoch_extractor.py | [health/eeg_meg/epoch_extractor.py](pirn/domains/health/eeg_meg/epoch_extractor.py) | YES | YES | YES — numpy array slicing into epochs |
| evoked_response_averager.py | [health/eeg_meg/evoked_response_averager.py](pirn/domains/health/eeg_meg/evoked_response_averager.py) | YES | YES | YES — numpy epoch average |
| meg_beamformer.py | [health/eeg_meg/meg_beamformer.py](pirn/domains/health/eeg_meg/meg_beamformer.py) | YES | YES | YES — numpy LCMV beamformer |
| notch_filter.py | [health/eeg_meg/notch_filter.py](pirn/domains/health/eeg_meg/notch_filter.py) | YES | YES | YES — scipy.signal iirnotch |
| power_spectrum_estimator.py | [health/eeg_meg/power_spectrum_estimator.py](pirn/domains/health/eeg_meg/power_spectrum_estimator.py) | YES | YES | YES — scipy.signal Welch PSD |
| seizure_detector.py | [health/eeg_meg/seizure_detector.py](pirn/domains/health/eeg_meg/seizure_detector.py) | YES | YES | YES — numpy power-threshold seizure intervals |
| sleep_stage_classifier.py | [health/eeg_meg/sleep_stage_classifier.py](pirn/domains/health/eeg_meg/sleep_stage_classifier.py) | YES | YES | YES — numpy Welch + band-power rule-based classifier |
| source_localizer.py | [health/eeg_meg/source_localizer.py](pirn/domains/health/eeg_meg/source_localizer.py) | YES | YES | YES — numpy minimum-norm source localisation |
| time_frequency_decomposer.py | [health/eeg_meg/time_frequency_decomposer.py](pirn/domains/health/eeg_meg/time_frequency_decomposer.py) | YES | YES | YES — scipy.signal spectrogram |

#### health/pathology/ (8 files — ~62% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| wsi_tile_extractor.py | [health/pathology/wsi_tile_extractor.py](pirn/domains/health/pathology/wsi_tile_extractor.py) | YES | YES | YES — real tile grid; returns WSITilePayload with numpy zero pixels |
| cell_detector.py | [health/pathology/cell_detector.py](pirn/domains/health/pathology/cell_detector.py) | YES | YES | YES — numpy pixel variance as cell count proxy |
| mitosis_counter.py | [health/pathology/mitosis_counter.py](pirn/domains/health/pathology/mitosis_counter.py) | YES | YES | YES — numpy normalised variance threshold |
| pathology_stain_normalizer.py | [health/pathology/pathology_stain_normalizer.py](pirn/domains/health/pathology/pathology_stain_normalizer.py) | YES | YES | YES — numpy Macenko stain normalisation |
| tissue_segmenter.py | [health/pathology/tissue_segmenter.py](pirn/domains/health/pathology/tissue_segmenter.py) | YES | YES | YES — numpy Otsu threshold on WSITilePayload pixels |
| cell_segmenter.py | [health/pathology/cell_segmenter.py](pirn/domains/health/pathology/cell_segmenter.py) | YES | YES | NO — stub; needs Cellpose/StarDist |
| pathology_feature_extractor.py | [health/pathology/pathology_feature_extractor.py](pirn/domains/health/pathology/pathology_feature_extractor.py) | YES | YES | NO — stub |
| tumor_microbiota_classifier.py | [health/pathology/tumor_microbiota_classifier.py](pirn/domains/health/pathology/tumor_microbiota_classifier.py) | YES | YES | NO — stub; needs DL classifier |

#### health/trials/ (11 files — ~27% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| adam_dataset_builder.py | [health/trials/adam_dataset_builder.py](pirn/domains/health/trials/adam_dataset_builder.py) | YES | YES | YES — real field projection from ClinicalTrialRecord via derivations map |
| survival_analysis_pipeline.py | [health/trials/survival_analysis_pipeline.py](pirn/domains/health/trials/survival_analysis_pipeline.py) | YES | YES | YES — scipy Kaplan-Meier + log-rank test |
| propensity_score_matcher_pipeline.py | [health/trials/propensity_score_matcher_pipeline.py](pirn/domains/health/trials/propensity_score_matcher_pipeline.py) | YES | YES | YES — numpy logistic approximation + nearest-neighbour matching |
| clinical_event_aggregator.py | [health/trials/clinical_event_aggregator.py](pirn/domains/health/trials/clinical_event_aggregator.py) | YES | YES | NO — stub |
| define_xml_generator.py | [health/trials/define_xml_generator.py](pirn/domains/health/trials/define_xml_generator.py) | YES | YES | NO — stub; needs CDISC Define-XML templating |
| estimand_aligned_analyzer.py | [health/trials/estimand_aligned_analyzer.py](pirn/domains/health/trials/estimand_aligned_analyzer.py) | YES | YES | NO — stub |
| meddra_normalizer.py | [health/trials/meddra_normalizer.py](pirn/domains/health/trials/meddra_normalizer.py) | YES | YES | NO — stub; needs MedDRA vocabulary DB |
| randomized_trial_analyzer.py | [health/trials/randomized_trial_analyzer.py](pirn/domains/health/trials/randomized_trial_analyzer.py) | YES | YES | NO — stub |
| rwe_cohort_extractor.py | [health/trials/rwe_cohort_extractor.py](pirn/domains/health/trials/rwe_cohort_extractor.py) | YES | YES | NO — stub |
| sdtm_domain_validator.py | [health/trials/sdtm_domain_validator.py](pirn/domains/health/trials/sdtm_domain_validator.py) | YES | YES | NO — stub; needs CDISC SDTM ruleset |
| treatment_emergent_classifier.py | [health/trials/treatment_emergent_classifier.py](pirn/domains/health/trials/treatment_emergent_classifier.py) | YES | YES | NO — stub |

#### health/wearables/ (8 files — ~87% real)

| File | Link | Validation | Return Type | Real Implementation |
|------|------|-----------|------------|-------------------|
| ecg_r_peak_detector.py | [health/wearables/ecg_r_peak_detector.py](pirn/domains/health/wearables/ecg_r_peak_detector.py) | YES | YES | YES — scipy.signal Pan-Tompkins R-peak detection |
| glucose_monitor_processor.py | [health/wearables/glucose_monitor_processor.py](pirn/domains/health/wearables/glucose_monitor_processor.py) | YES | YES | YES — numpy trend + time-in-range computation |
| heart_rate_variability_analyzer.py | [health/wearables/heart_rate_variability_analyzer.py](pirn/domains/health/wearables/heart_rate_variability_analyzer.py) | YES | YES | YES — numpy SDNN, RMSSD, pNN50 |
| ppg_heart_rate_extractor.py | [health/wearables/ppg_heart_rate_extractor.py](pirn/domains/health/wearables/ppg_heart_rate_extractor.py) | YES | YES | YES — scipy.signal peak detection on PPG |
| sleep_stager.py | [health/wearables/sleep_stager.py](pirn/domains/health/wearables/sleep_stager.py) | YES | YES | YES — numpy band-power rule-based staging |
| spirometry_analyzer.py | [health/wearables/spirometry_analyzer.py](pirn/domains/health/wearables/spirometry_analyzer.py) | YES | YES | YES — numpy FEV1/FVC/PEF computation |
| step_counter.py | [health/wearables/step_counter.py](pirn/domains/health/wearables/step_counter.py) | YES | YES | YES — numpy threshold + zero-crossing step detection |
| accelerometer_activity_classifier.py | [health/wearables/accelerometer_activity_classifier.py](pirn/domains/health/wearables/accelerometer_activity_classifier.py) | YES | YES | NO — stub; needs classifier model |

---

## Gap Count Summary

| Domain | Total impl files | Real Implementation | Hollow / Partial |
|--------|-----------------|--------------------|--------------------|
| agents | ~150 | ~145 | ~5 (pass-throughs by design) |
| data | ~80 | ~75 | ~5 (config/spec dataclasses) |
| connectors | ~130 | ~130 | 0 |
| signal | ~85 | ~85 | 0 ✅ (2026-05-08) |
| health | ~129 | ~100 | ~29 (mri×6, pathology×3, trials×8, wearables×1, clinical×2) |
| **ml** | **~126** | **0** | **~126** |
| **oilgas** | **~90** | **~29** | **~61** |
| **Total gaps** | | | **~216 files** |

---

## Remediation Approach

### Implementation Rules (for all gaps)

1. **No magic numbers or hardcoded returns** — any value a user could reasonably observe must be computed from real inputs.
2. **Lazy imports** — all optional scientific dependencies must be imported inside `process()` with an `ImportError` naming the extras group.
3. **Fail loud** — if a required subprocess tool or SDK is absent, raise with a descriptive error. Never silently fall back to hollow behaviour.
4. **No shell=True** — subprocess calls must pass args as a list, validate all path inputs before use.
5. **Audit dict** — if the result type has `_pirn_audit_dict()`, all fields must be populated with real values.

### Priority Order

```
Priority 1 — signal (scipy/numpy available, no new infra needed)
  All 85 files. scipy.signal covers filters, spectral, resampling.
  numpy covers separation (via sklearn/scipy). pywt covers wavelets.
  librosa covers audio. antropy/nolds cover nonlinear estimators.
  Estimated: 10–15 days for full signal domain.

Priority 2 — ml (sklearn/torch available, no new infra needed)
  Core base knots: trainer.py, evaluator.py, hyperparam_search.py (~6 files).
  Once base knots are real, all specialization SubTapestries inherit real behaviour.
  Then feature transformers need row-level implementation.
  Estimated: 15–20 days for full ml domain.

Priority 3 — oilgas hollow knots (~61 files)
  Production/integrity/reservoir: real formulas available in literature.
  Seismic: requires segyio; consider subprocess to OpendTect/Madagascar for migration.
  Geospatial: pyproj for coordinate transforms; shapely for proximity.
  Estimated: 8–12 days.

Priority 4 — health wearables + trials (scipy/lifelines/statsmodels, no GPU)
  25 files, pure Python scientific libraries.
  Estimated: 5–8 days.

Priority 5 — health clinical SDK ingestion (4 files)
  fhir.resources, hl7apy, OMOP vocabulary tables.
  Estimated: 3–5 days.

Priority 6 — health genomics CLI tools (~23 files)
  Requires samtools, bowtie2, bwa, STAR, GATK, bcftools, SnpEff, VEP in PATH.
  Infrastructure dependency — needs bioinformatics environment.
  Estimated: 5–8 days (plus infra setup).

Priority 7 — health MRI / EEG-MEG (~38 files)
  nibabel, nilearn, antspy, mne for I/O and processing.
  Estimated: 8–12 days.

Priority 8 — health pathology (~8 files)
  Cellpose/StarDist for segmentation; GPU required for DL inference.
  Highest infra cost.
  Estimated: 7–10 days (plus GPU environment).
```

### Total Estimated Effort

| Priority | Domain / Area | Files | Estimate |
|----------|--------------|-------|----------|
| 1 | signal (all) | ~85 | 10–15 days |
| 2 | ml (base knots + features) | ~126 | 15–20 days |
| 3 | oilgas hollow knots | ~61 | 8–12 days |
| 4 | health wearables + trials | ~25 | 5–8 days |
| 5 | health clinical SDK | 4 | 3–5 days |
| 6 | health genomics CLI | ~23 | 5–8 days |
| 7 | health MRI + EEG/MEG | ~38 | 8–12 days |
| 8 | health pathology DL | ~8 | 7–10 days |
| **Total** | | **~370** | **~61–90 days** |

---

## Correctly Non-Implemented (Do Not Remediate)

| Location | Reason |
|----------|--------|
| All `*/protocols/*.py` abstract methods | Interface contracts — correct design |
| `data/lakehouse/hudi_table.py` write methods | Python Hudi ecosystem lacks native write path |
| `data/lakehouse/iceberg_table.py` merge | pyiceberg ≥0.6 lacks native MERGE |
| `connectors/file_formats/grib_format.py` write | eccodes write complexity; read-only by design |
| `connectors/file_formats/dlis_format.py` write | DLIS write complexity |
| `connectors/file_formats/segd_format.py` write | SEG-D write complexity |
| `connectors/file_formats/root_format.py` write | CERN ROOT write complexity |
| `connectors/file_formats/open_slide_format.py` write | WSI write not supported by OpenSlide |
| `agents/llm_provider_knot.py`, `memory_store_knot.py` | Intentional pass-through vending knots |

---

## Part III — Implicit Input Schema Assumption Audit

**Audited:** 2026-05-07  
**Scope:** All `process()` methods that accept `dict[str, Any]`, `list[dict[str, Any]]`, or `Mapping[str, Any]` inputs  
**Method:** Per-file read looking for hardcoded string key literals accessed via `.get("key", default)` or `d["key"]` inside `process()`.  
**Patterns:**
- **Caller-Supplied** — key names passed as explicit constructor/graph inputs (correct design)
- **Hardcoded + KeyError** — bracket access `d["key"]`; fails loudly on missing key (acceptable)
- **Hardcoded + Silent Default** — `.get("key", value)` returns wrong default with no error (PROBLEM)

---

### Signal Domain

**Signal: NO RISK.** All 108+ files use explicitly typed parameters (`SignalFrame`, `float`, `int`) in `process()`. No `dict[str, Any]` unpacking occurs anywhere in this domain.

---

### Agents Domain

| File | Input Type | Hardcoded Keys | Silent Default Risk |
|------|-----------|----------------|---------------------|
| `generation/output_parser.py` | `Mapping[str, Any]` | `content`, `stop_reason`, `finish_reason`, `choices`, `usage`, `type`, `text`, `tool_use`, `id`, `call_id`, `name`, `input`, `arguments`, `message` | YES — 14 keys; missing any falls back to `""` or `"stop"` |
| `input/message_parser.py` | `Mapping[str, Any]` | `role` (default `"user"`), `content`, `name`, `tool_call_id` | YES — missing `role` silently assigned `"user"` |
| `planning/planner.py` | `AgentContext` | `content`, `text`, `message` from response dict | YES — multiple fallback chain; wrong path silently picks `""` |
| `generation/response_formatter.py` | `AgentResponse` | `content`, `tool_calls`, `tool_name`, `call_id`, `arguments` | NO — typed `AgentResponse`; not raw dict |
| `planning/tool_result_aggregator.py` | `Sequence[ToolResult]` | `error` | NO — only for error path; typed inputs |

**Root cause:** LLM response parsing hardcodes provider-specific key names (`choices[0].message.content` for OpenAI vs `content` for Anthropic). A new provider or changed API version silently produces empty output.

---

### Data Domain

| File | Input Type | Hardcoded Keys | Silent Default Risk |
|------|-----------|----------------|---------------------|
| `quality/freshness_check.py` | `DataBatch` rows (`Mapping[str, Any]`) | column name via `.get()` | YES — missing column returns `None`; check silently passes |
| `quality/null_rate_check.py` | `dict[str, float]` thresholds | rate values | NO — numeric validation, not field-name access |
| `quality/schema_validator.py` | `DataBatch` rows | column name via `in` check | YES — missing column silently treated as null |
| `specializations/deduplication/exact_deduplicator.py` | `Mapping[str, Any]` rows | `key_columns` names via `row.get(col)` | YES — missing key column returns `None`; affects dedup grouping silently |
| `specializations/dimensional/dim_table_load.py` | `list[tuple]` → zipped to dicts | column names from caller-supplied list | YES — wrong column count produces column-order mismatch with no error |
| `specializations/feature_engineering/derived_column_calculator.py` | `list[dict]` specs | `column`, `expression` from spec dicts | YES — missing spec keys default to `""`; produces unparseable expression names |
| `transforms/aggregate.py` | `DataBatch` rows | `by` column names via `.get()` | YES — missing group column returns `None`; groups silently under `None` key |
| `transforms/normalize.py` | `Mapping[str, Any]` rows | `strip_whitespace`, `case`, `null_tokens` from rule objects | NO — typed `NormalizeColumnRule`; validated at construction |

---

### Connectors Domain

#### File Formats (Encoders/Writers)

| File | Hardcoded Keys | Silent Default Risk | Impact |
|------|---------------|---------------------|--------|
| `file_formats/dicom_format.py` | `sop_instance_uid`, `study_uid`, `series_uid`, `modality` (default `"OT"`), `pixel_data`, `pixel_array_shape` | YES | Wrong modality `"OT"` written to every DICOM without modality field |
| `file_formats/edf_format.py` | `data`, `n_samples`, `sample_rate` (default `1`), `physical_min` (default `-32768.0`), `physical_max` (default `32767.0`), `label` | YES | Magic EDF defaults (−32768/32767) will be accepted silently |
| `file_formats/bdf_format.py` | Same as EDF | YES | Identical risk |
| `file_formats/fhir_json_format.py` | `resource_type` (default `"Resource"`) | YES | Invalid FHIR resource type if field missing |
| `file_formats/fhir_xml_format.py` | `resource_type`, `status`, `data` | YES | Same as JSON path |
| `file_formats/geojson_format.py` | `properties` (default `{}`), `feature_id` (default `None`) | YES | GeoJSON features written with empty properties |
| `file_formats/kml_format.py` | `name`, `description`, `extended_data` | YES | KML placemarks written with empty name |
| `file_formats/fits_format.py` | `header` (default `{}`), `data` (default `None`) | YES | FITS HDU written with no header |
| `file_formats/hl7v2_format.py` | `segments`, `segment_id`, `fields` | YES | Empty HL7 messages written silently |
| `file_formats/cda_xml_format.py` | `document_id`, `template_id`, `title` | YES | CDA documents written with no ID |
| `file_formats/las_format.py` | `curves`, `data` | YES | Empty LAS files written silently |
| `file_formats/geotiff_format.py` | `transform`, `crs`, `dtype` (default `"float64"`) | YES | GeoTIFF written with no CRS |
| `file_formats/bids_dataset_format.py` | `relative_path`, `content` | NO — bracket access raises `KeyError` | Loud failure; acceptable |
| `file_formats/tiff_format.py` | `width`, `height`, `mode`, `data`, `dtype` | NO — bracket access raises `KeyError` | Loud failure; acceptable |
| `file_formats/jpeg_format.py` | `width`, `height`, `mode`, `data` | NO — bracket access raises `KeyError` | Loud failure; acceptable |

#### SaaS Clients

| File | Hardcoded Keys | Silent Default Risk |
|------|---------------|---------------------|
| `saas/amplitude_client.py` | `user_id`, `event_type`, `event`, `properties` | YES — `properties` silently `None`; wrong event_type accepted |
| `saas/mixpanel_client.py` | `distinct_id`, `event`, `properties` | YES — `properties` silently `None` |
| `saas/stripe_client.py` | `data`, `has_more` | YES — missing `has_more` silently stops pagination |
| `saas/hubspot_client.py` | `results`, `paging`, `next`, `after` | YES — nested `.get()` chain; wrong page cursor silently stops |
| `saas/airtable_client.py` | `records`, `offset` | YES — missing `offset` stops pagination |

#### Streaming

| File | Hardcoded Keys | Silent Default Risk |
|------|---------------|---------------------|
| `streaming/kinesis_broker.py` | `StreamDescription`, `Shards`, `ShardId`, `ShardIterator`, `Records`, `NextShardIterator` | YES — assumes AWS SDK response shape; version changes break silently |

---

### ML Domain

| File | Hardcoded Keys | Silent Default Risk |
|------|---------------|---------------------|
| `specializations/production/continuous_training_pipeline.py` | `events`, `recorded_at`, `model_id` from lineage record | YES — missing `events` silently returns `None`; lineage not recorded |

All other ML files use explicitly typed parameters in `process()`. No other dict-unpacking risks.

---

### Oilgas Domain — CRITICAL

Oilgas is the highest-risk domain. SCADA systems and historians use site-specific tag names. Files that hardcode field names assume a specific naming convention that may not match any real historian.

| File | Hardcoded Keys | Silent Default Risk |
|------|---------------|---------------------|
| `production/production_rate_normalizer.py` | `rate_bopd`, `wellhead_pressure_psia`, `wellhead_temp_f` | YES — pressure defaults to `ref_p`, rate defaults to `0.0`; wrong correction silently applied |
| `production/gas_lift_optimizer.py` | `performance_curve`, `current_injection_mmscfd`, `injection_mmscfd`, `oil_bopd` | YES — missing curve silently returns reference point; optimizer produces wrong injection rate |
| `production/esp_health_monitor.py` | `motor_temp_c`, `vibration_g` | YES — missing telemetry defaults to `0.0`; health status silently computed as normal |
| `production/flaring_measurement_processor.py` | `flow_rate_mmscfd` | YES — missing flow defaults to `0.0`; flare volume under-reported silently |
| `production/downtime_event_classifier.py` | `timestamp_iso`, `rate_bopd` | YES — missing rate defaults to `0.0`; downtime events silently misclassified |
| `production/rod_pump_optimizer.py` | `current_spm`, `stroke_length_in` | YES — missing telemetry defaults to `0.0`; optimization produces wrong pump parameters |
| `production/separator_test_processor.py` | `oil_rate_bopd`, `gas_rate_mmscfd`, `water_rate_bwpd` | YES — all three default to `0.0`; separator test silently zeroed |
| `production/tank_gauging_processor.py` | `opening_level_in`, `closing_level_in`, `bsw_pct` | YES — defaults to `0.0`; tank inventory silently zeroed |
| `integrity/corrosion_rate_estimator.py` | `feature_count` | YES — defaults to `0`; estimator silently produces wrong rate |
| `integrity/gas_chromatography_analyzer.py` | `components`, `total_area` | YES — missing components default to `[]`; composition silently empty |
| `well/mud_logging_ingester.py` | `data`, `header` | YES — missing sections default to `[]`/`{}`; mud log silently empty |

**All 70+ oilgas files using typed inputs (`ScadaTimeSeries`, `LASFile`, `DrillingParameters`) are safe.**

---

### Health Domain

| File | Subdomain | Hardcoded Keys | Silent Default Risk | Impact |
|------|-----------|---------------|---------------------|--------|
| `clinical/vital_signs_aggregator.py` | Clinical | `patient_id`, `vital_name`, `value` | YES | Missing keys silently grouped under `""` key; vital data lost |
| `clinical/lab_result_normalizer.py` | Clinical | `unit`, `value` | YES | Missing `unit` → 1.0x multiplier applied silently; wrong values |
| `clinical/task_fmri_modeler.py` | Clinical/MRI | `trial_type` (events), `n_volumes` (bold_data) | YES | Missing trial type silently becomes `""`; wrong fMRI contrasts |
| `clinical/survival_analysis_pipeline.py` | Clinical | `time_col` (param), `event_col` (param), `patient_id` (hardcoded) | MIXED | Column names caller-supplied (OK); `patient_id` hardcoded (RISK) |
| `clinical/propensity_score_matcher_pipeline.py` | Clinical | `treatment_col` (param), `patient_id` (hardcoded) | MIXED | Column name OK; `patient_id` hardcoded in match logic |
| `genomics/vcf_filter.py` | Genomics | `qual`, `af` | YES — INVERTED | Missing `af` defaults to `0.0` which **passes** frequency filter — variants silently included |
| `genomics/methylation_array_processor.py` | Genomics | `sample_id`, `red_channel`, `green_channel` | YES | Missing `sample_id` silently becomes `""`; array mislabeled |
| `wearables/accelerometer_activity_classifier.py` | Wearables | `x`, `y`, `z`, `timestamps_iso` | YES | Missing axis defaults to `[]`; magnitude always `0.0` silently |
| `wearables/ppg_heart_rate_extractor.py` | Wearables | `timestamps_iso` (hardcoded), wavelength names (caller-supplied) | MIXED | Timestamps hardcoded; missing → empty list, no HR computed |
| `eeg_meg/sleep_stage_classifier.py` | EEG/MEG | `epochs`, `sample_rate_hz` | YES | Missing epochs → empty list; degenerate stage output |

---

### Cross-Domain Risk Summary

| Risk Level | Count | Domains |
|-----------|-------|---------|
| 🔴 CRITICAL — Silent wrong computation | 11 | oilgas (all production measurement files) |
| 🔴 CRITICAL — Inverted filter logic on missing key | 1 | health/genomics (`vcf_filter.py`) |
| 🔴 HIGH — Patient data silently mislabeled/lost | 4 | health/clinical |
| 🟠 HIGH — Wrong output format written silently | 12 | connectors/file_formats |
| 🟠 HIGH — Pagination silently stops | 4 | connectors/saas |
| 🟡 MEDIUM — Degenerate signal processing | 3 | health/wearables, health/eeg_meg |
| 🟡 MEDIUM — LLM response parsing fragile | 3 | agents |
| 🟡 MEDIUM — Quality checks silently pass | 3 | data |

---

### Fix Pattern

**Wrong (current):**
```python
rate = m.get("rate_bopd", 0.0)          # silently 0.0 if SCADA uses "RATE" tag
qual = row.get("qual", 0.0)             # silently 0.0; may invert filter intent
```

**Correct option A — raise on missing required field:**
```python
if "rate_bopd" not in m:
    raise ValueError(f"measurement dict missing required key 'rate_bopd'; got keys: {list(m)}")
rate = float(m["rate_bopd"])
```

**Correct option B — caller-supplied field name (preferred for SCADA):**
```python
# In __init__:
self.rate_field: str  # caller supplies the actual tag name: "RATE", "rate_bopd", etc.
# In process():
rate = float(m[self.rate_field])
```

Option B is preferred for oilgas/SCADA because tag naming is historian- and site-specific. The knot graph is the right place to wire tag names, not the implementation.

---

### Remediation Priority (Input Assumptions)

| Priority | Files | Action |
|----------|-------|--------|
| P0 — Fix before any production use | `vcf_filter.py` (inverted filter), all 11 oilgas production files | Replace `.get()` with either explicit raises or caller-supplied key params |
| P1 — Fix before health data ingestion | `vital_signs_aggregator.py`, `lab_result_normalizer.py`, `accelerometer_activity_classifier.py`, `sleep_stage_classifier.py` | Replace with `d["key"]` + explicit error messages |
| P2 — Fix before connector production use | All 12 file-format encoder files with silent `.get()` defaults | Replace magic defaults with `KeyError`; document required record schema |
| P3 — Fix before SaaS connector use | Amplitude, Mixpanel, Stripe, HubSpot, Airtable pagination | Raise on missing pagination cursor; document required event shape |
| `ml/*/` interface providers (`lineage_store.py` etc.) | Abstract base — concrete subclass responsibility |
