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

### Group 1 — clinical/_dedup_rx_cuis.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/_dedup_rx_cuis.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 2 — clinical/_pass_through.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/_pass_through.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 3 — clinical/clinical_data_quality_gate.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/clinical_data_quality_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | [x] | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 4 — clinical/clinical_nlp_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/clinical_nlp_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 5 — clinical/clinical_trial_eligibility_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/clinical_trial_eligibility_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 6 — clinical/diagnosis_code_rollup.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/diagnosis_code_rollup.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 7 — clinical/encounter_timeline_assembler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/encounter_timeline_assembler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 8 — clinical/fhir_patient_ingestor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/fhir_patient_ingestor.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 9 — clinical/hl7v2_message_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/hl7v2_message_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 10 — clinical/icd10_code_validator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/icd10_code_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 11 — clinical/lab_result_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/lab_result_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 12 — clinical/loinc_mapper.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/loinc_mapper.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 13 — clinical/medication_reconciliation_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/medication_reconciliation_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 14 — clinical/omop_cdm_mapper.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/omop_cdm_mapper.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 15 — clinical/patient_cohort_builder.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/patient_cohort_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 16 — clinical/phi_redactor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/phi_redactor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 17 — clinical/readmission_risk_scorer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/readmission_risk_scorer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 18 — clinical/rxnorm_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/rxnorm_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 19 — clinical/snomed_ct_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/snomed_ct_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 20 — clinical/vital_signs_aggregator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/clinical/vital_signs_aggregator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 21 — eeg_meg/artifact_remover.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/artifact_remover.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 22 — eeg_meg/bandpass_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/bandpass_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 23 — eeg_meg/coherence_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/coherence_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 24 — eeg_meg/connectivity_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/connectivity_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 25 — eeg_meg/eeg_ica_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/eeg_ica_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 26 — eeg_meg/eeg_montage_applier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/eeg_montage_applier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 27 — eeg_meg/eeg_raw_ingestor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/eeg_raw_ingestor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 28 — eeg_meg/epoch_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/epoch_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 29 — eeg_meg/evoked_response_averager.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/evoked_response_averager.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 30 — eeg_meg/meg_beamformer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/meg_beamformer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 31 — eeg_meg/meg_raw_ingestor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/meg_raw_ingestor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 32 — eeg_meg/notch_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/notch_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 33 — eeg_meg/power_spectrum_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/power_spectrum_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 34 — eeg_meg/seizure_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/seizure_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 35 — eeg_meg/sleep_stage_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/sleep_stage_classifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 36 — eeg_meg/source_localizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/source_localizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 37 — eeg_meg/time_frequency_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/eeg_meg/time_frequency_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 38 — genomics/adapter_trimmer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/adapter_trimmer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 39 — genomics/bam_sort_indexer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/bam_sort_indexer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 40 — genomics/bcftools_caller.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/bcftools_caller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 41 — genomics/bowtie2_aligner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/bowtie2_aligner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 42 — genomics/bulk_atac_seq_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/bulk_atac_seq_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 43 — genomics/bwa_aligner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/bwa_aligner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 44 — genomics/cnv_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/cnv_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 45 — genomics/differential_expression_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/differential_expression_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 46 — genomics/expression_quantifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/expression_quantifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 47 — genomics/fastq_quality_controller.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/fastq_quality_controller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 48 — genomics/gatk_caller.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/gatk_caller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 49 — genomics/gene_set_enrichment_runner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/gene_set_enrichment_runner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 50 — genomics/genomics_qc_gate.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/genomics_qc_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 51 — genomics/gvcf_combiner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/gvcf_combiner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 52 — genomics/methylation_array_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/methylation_array_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 53 — genomics/multi_omics_integrator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/multi_omics_integrator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 54 — genomics/pathway_enricher.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/pathway_enricher.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 55 — genomics/pharmacogenomic_scorer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/pharmacogenomic_scorer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 56 — genomics/single_cell_clusterer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/single_cell_clusterer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 57 — genomics/snpeff_annotator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/snpeff_annotator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 58 — genomics/star_aligner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/star_aligner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 59 — genomics/structural_variant_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/structural_variant_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 60 — genomics/vcf_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/vcf_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 61 — genomics/vcf_merger.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/vcf_merger.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 62 — genomics/vep_annotator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/genomics/vep_annotator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 63 — mri/atlas_aligner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/atlas_aligner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 64 — mri/bias_field_corrector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/bias_field_corrector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 65 — mri/bids_converter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/bids_converter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 66 — mri/brain_age_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/brain_age_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 67 — mri/brain_mask_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/brain_mask_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 68 — mri/cortical_thickness_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/cortical_thickness_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 69 — mri/dicom_ingestor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/dicom_ingestor.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 70 — mri/dti_preprocessor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/dti_preprocessor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 71 — mri/functional_connectivity_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/functional_connectivity_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 72 — mri/image_registrar.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/image_registrar.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 73 — mri/intensity_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/intensity_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 74 — mri/lesion_segmenter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/lesion_segmenter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 75 — mri/motion_corrector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/motion_corrector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 76 — mri/mri_quality_controller.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/mri_quality_controller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 77 — mri/nifti_converter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/nifti_converter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 78 — mri/radiomics_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/radiomics_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 79 — mri/region_of_interest_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/region_of_interest_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 80 — mri/spatial_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/spatial_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 81 — mri/task_fmri_modeler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/task_fmri_modeler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 82 — mri/vbm_morphometry_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/vbm_morphometry_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 83 — mri/volumetric_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/volumetric_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 84 — mri/white_matter_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/mri/white_matter_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 85 — pathology/cell_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/cell_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 86 — pathology/cell_segmenter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/cell_segmenter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 87 — pathology/mitosis_counter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/mitosis_counter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 88 — pathology/pathology_feature_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/pathology_feature_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 89 — pathology/pathology_stain_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/pathology_stain_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 90 — pathology/tissue_segmenter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/tissue_segmenter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 91 — pathology/tumor_microbiota_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/tumor_microbiota_classifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 92 — pathology/wsi_tile_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/pathology/wsi_tile_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 93 — trials/adam_dataset_builder.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/adam_dataset_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 94 — trials/clinical_event_aggregator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/clinical_event_aggregator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 95 — trials/define_xml_generator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/define_xml_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 96 — trials/estimand_aligned_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/estimand_aligned_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 97 — trials/meddra_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/meddra_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 98 — trials/propensity_score_matcher_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/propensity_score_matcher_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 99 — trials/randomized_trial_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/randomized_trial_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 100 — trials/rwe_cohort_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/rwe_cohort_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 101 — trials/sdtm_domain_validator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/sdtm_domain_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 102 — trials/survival_analysis_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/survival_analysis_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 103 — trials/treatment_emergent_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/trials/treatment_emergent_classifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 104 — wearables/accelerometer_activity_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/accelerometer_activity_classifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 105 — wearables/ecg_r_peak_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/ecg_r_peak_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 106 — wearables/glucose_monitor_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/glucose_monitor_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 107 — wearables/heart_rate_variability_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/heart_rate_variability_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 108 — wearables/ppg_heart_rate_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/ppg_heart_rate_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 109 — wearables/sleep_stager.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/sleep_stager.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 110 — wearables/spirometry_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/spirometry_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 111 — wearables/step_counter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/health/wearables/step_counter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
