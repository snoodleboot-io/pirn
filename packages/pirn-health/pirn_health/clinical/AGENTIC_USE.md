Processes clinical data — HL7v2 parsing, ICD-10/SNOMED CT/RxNorm/LOINC coding, PHI redaction, NLP extraction from notes, OMOP mapping, and patient cohort building — does NOT query EHR systems directly; use DatabaseQuerySource with the appropriate connection pool.

## Mental model

Clinical knots are stateless transforms over `ClinicalRecord` (`pirn_health.types.clinical_record`: `patient_id`, `encounter_id`, `observation_codes`, `observed_at`, `source_system`) or over plain code/row sequences. Coding knots (`ICD10CodeValidator`, `RxNormNormalizer`, `SnomedCTNormalizer`, `LOINCMapper`, `DiagnosisCodeRollup`) are pure lookup-and-validate steps; the normalisers take the code map as an input rather than bundling a terminology release. `ClinicalNLPExtractor` extracts structured facts from free text through a `HealthLLMProvider`.

`ClinicalDataQualityCheck` sits between ingestion and downstream analytics. It raises `ClinicalDataQualityError` when the fraction of complete records drops below `min_completeness`, so bad data fails loudly before reaching cohort or risk models. All other knots are unconditional — quality enforcement belongs in the check.

`ClinicalRecord` may carry raw identifiers until `PHIRedactor` (or an assembler that hashes at construction time, such as `FhirPatientAssembler`) runs; its audit dict never includes `patient_id` or `encounter_id`. `Hl7v2Format` at the connector layer redacts PID name, date of birth, and address fields on decode.

Several knots are marked `_is_stub = True` (`HL7v2MessageParser`, `OMOPCDMMapper`, `ClinicalNLPExtractor`, `LOINCMapper`, `LabResultNormalizer`, `ReadmissionRiskScorer`): wired and testable end-to-end, not production-quality.

## Source map

```
pirn_health/clinical/
├── clinical_data_quality_check.py        ClinicalDataQualityCheck         — completeness check; raises ClinicalDataQualityError on failure
├── clinical_data_quality_error.py        ClinicalDataQualityError         — typed error for quality check failures
├── clinical_nlp_extractor.py             ClinicalNLPExtractor             — LLM extraction of diagnoses/medications/vitals from note text
├── clinical_record_pass_through.py       ClinicalRecordPassThrough        — identity knot seeding PatientCohortBuilder's filter chain
├── clinical_trial_eligibility_filter.py  ClinicalTrialEligibilityFilter   — filters records against named predicate criteria
├── diagnosis_code_rollup.py              DiagnosisCodeRollup              — rolls ICD-10 codes up to a shorter prefix
├── encounter_timeline_assembler.py       EncounterTimelineAssembler       — per-patient records sorted by observed_at
├── hl7v2_message_parser.py               HL7v2MessageParser               — parses an HL7v2 message string into a ClinicalRecord
├── icd10_code_validator.py               ICD10CodeValidator               — True iff every code matches the ICD-10-CM structure
├── lab_result_normalizer.py              LabResultNormalizer              — converts lab values to a target unit via a conversion map
├── loinc_mapper.py                       LOINCMapper                      — maps lab test names to LOINC codes via a supplied map
├── medication_reconciliation_pipeline.py MedicationReconciliationPipeline — SubTapestry: RxNorm normalise then dedup
├── omop_cdm_mapper.py                    OMOPCDMMapper                    — maps a ClinicalRecord to OMOP CDM rows
├── patient_cohort_builder.py             PatientCohortBuilder             — SubTapestry chaining eligibility filter stages
├── phi_hasher.py                         PhiHasher                        — salted SHA-256 identifier hashing shared by PHIRedactor and FhirPatientAssembler
├── phi_redactor.py                       PHIRedactor                      — replaces patient/encounter ids with salted hash tokens
├── readmission_risk_scorer.py            ReadmissionRiskScorer            — per-patient readmission risk score
├── rx_cui_deduplicator.py                RxCuiDeduplicator                — order-preserving RxCUI dedup stage of MedicationReconciliationPipeline
├── rxnorm_normalizer.py                  RxNormNormalizer                 — maps drug names to RxCUIs via a supplied map
├── snomed_ct_normalizer.py               SnomedCTNormalizer               — maps ICD codes to SNOMED CT via a supplied map
└── vital_signs_aggregator.py             VitalSignsAggregator             — per-patient summary statistics of vitals rows
```

## Canonical pattern

HL7v2 message → parse → redact PHI → OMOP rows, with ICD-10 validation of the diagnosis codes:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_health.clinical.hl7v2_message_parser import HL7v2MessageParser
from pirn_health.clinical.icd10_code_validator import ICD10CodeValidator
from pirn_health.clinical.omop_cdm_mapper import OMOPCDMMapper
from pirn_health.clinical.phi_redactor import PHIRedactor

with Tapestry() as t:
    hl7_message = Parameter("hl7_message", str)
    diagnosis_codes = Parameter("diagnosis_codes", list[str])
    salt = Parameter("salt", str)

    parsed = HL7v2MessageParser(
        message=hl7_message,
        _config=KnotConfig(id="parse"),
    )
    redacted = PHIRedactor(
        record=parsed,
        salt=salt,
        _config=KnotConfig(id="redact"),
    )
    OMOPCDMMapper(
        record=redacted,
        _config=KnotConfig(id="omop"),
    )
    ICD10CodeValidator(
        codes=diagnosis_codes,
        _config=KnotConfig(id="icd_valid"),
    )

result = await t.run(RunRequest(parameters={
    "hl7_message": raw_hl7_text,
    "diagnosis_codes": ["E11.9", "I10"],
    "salt": linkage_salt,
}))
omop_rows = result.outputs["omop"]
```

## Anti-patterns

**Letting raw identifiers reach sinks** — `HL7v2MessageParser` and other record producers do not hash identifiers. Wire `PHIRedactor` (with a stable, secret salt so linkage survives across runs) before any knot that writes records out.

**Treating the static-map normalisers as terminology services** — `RxNormNormalizer`, `SnomedCTNormalizer`, and `LOINCMapper` only translate what is in the `mapping` you pass. They do not expand hierarchies or resolve synonyms; load and pass a maintained map.

**Using `ReadmissionRiskScorer` as a clinical decision support tool** — it is a stub heuristic (score from observation-code count), not a validated model. Use it only to exercise pipeline wiring.

## Constraints and gotchas

- `ICD10CodeValidator` checks structure against the ICD-10-CM regex only; it does not confirm a code exists in a release.
- `ClinicalNLPExtractor` requires a `HealthLLMProvider` input (`pirn_health.health_llm_provider`).
- `PatientCohortBuilder` and `MedicationReconciliationPipeline` are `SubTapestry` knots; `PatientCohortBuilder` takes `stages` as a mapping of stage name → criteria mapping, each applied in order by a `ClinicalTrialEligibilityFilter`.
- `RxCuiDeduplicator` is the dedup stage `MedicationReconciliationPipeline` wires internally; wire the pipeline rather than the stage unless you already hold normalised RxCUIs.
- `ClinicalDataQualityCheck` raises `ClinicalDataQualityError` — catch it at the tapestry call site if partial results are acceptable.
- `EncounterTimelineAssembler` sorts each patient's records by `observed_at` ascending, stable across equal timestamps.
- Install: `pip install "pirn-health[health]"`

## Quick reference

| Task | How |
|---|---|
| Parse HL7v2 message | `HL7v2MessageParser` |
| Redact identifiers | `PHIRedactor` |
| Validate diagnosis codes | `ICD10CodeValidator` |
| Roll codes up to categories | `DiagnosisCodeRollup` |
| Map drug names to RxNorm | `RxNormNormalizer`, or `MedicationReconciliationPipeline` to also dedup |
| Map ICD codes to SNOMED CT | `SnomedCTNormalizer` |
| Map lab tests to LOINC / normalise units | `LOINCMapper` / `LabResultNormalizer` |
| Extract entities from notes | `ClinicalNLPExtractor` |
| Build patient cohort | `PatientCohortBuilder` (stages of `ClinicalTrialEligibilityFilter` criteria) |
| Map to OMOP CDM | `OMOPCDMMapper` |
| Score readmission risk | `ReadmissionRiskScorer` |
| Chronological encounter view | `EncounterTimelineAssembler` |
| Summarise vitals | `VitalSignsAggregator` |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
