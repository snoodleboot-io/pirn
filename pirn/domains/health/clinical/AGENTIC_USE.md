Processes clinical data — HL7v2 parsing, ICD/SNOMED/RxNorm coding, NLP extraction from notes, and patient cohort building — does NOT query EHR systems directly; use DatabaseQuerySource with the appropriate connection pool.

## Mental model

Clinical knots are stateless transforms: each accepts structured or semi-structured clinical data and emits normalised, coded records. Coding knots (`Icd10CodeValidator`, `RxNormMapper`, `SnomedHierarchyExpander`) are pure lookup-and-validate steps; NLP knots (`ClinicalNlpExtractor`, `NoteSectionSplitter`) extract structured facts from unstructured text.

The `ClinicalDataQualityGate` sits between ingestion and downstream analytics. It raises `ClinicalDataQualityError` when records violate configured thresholds (missing required fields, out-of-range values, invalid codes) so that bad data fails loudly before reaching cohort or risk models. All other knots are unconditional — quality enforcement belongs in the gate.

PHI passes through this layer only as already-redacted fields originating from the connector layer (`Hl7v2Format`, `FhirJsonFormat`, etc.). These knots do not re-introduce raw identifiers.

## Source map

```
pirn/domains/health/clinical/
├── clinical_data_quality_error.py       ClinicalDataQualityError         — typed error for quality gate failures
├── clinical_data_quality_gate.py        ClinicalDataQualityGate          — quality gate; raises ClinicalDataQualityError on failure
├── clinical_nlp_extractor.py            ClinicalNlpExtractor             — NLP extraction of clinical entities from free text
├── clinical_trial_eligibility_filter.py ClinicalTrialEligibilityFilter   — filters patients against trial inclusion/exclusion criteria
├── _dedup_rx_cuis.py                    (internal)                        — RxNorm CUI deduplication helper; not a public knot
├── diagnosis_code_rollup.py             DiagnosisCodeRollup              — rolls ICD-10 leaf codes up to ancestor categories
├── encounter_timeline_assembler.py      EncounterTimelineAssembler       — builds chronological encounter timelines per patient
├── hl7v2_message_parser.py              Hl7v2MessageParser               — parses decoded HL7v2 records into domain events
├── icd10_code_validator.py              Icd10CodeValidator               — validates ICD-10-CM/PCS codes against current release
├── lab_result_normalizer.py             LabResultNormalizer              — normalises LOINC-coded lab results to SI units
├── medication_reconciler.py             MedicationReconciler             — reconciles medication lists across encounters
├── medication_standardizer.py           MedicationStandardizer           — maps free-text drug names to RxNorm CUIs
├── note_section_splitter.py             NoteSectionSplitter              — splits clinical note text into labelled sections
├── patient_cohort_builder.py            PatientCohortBuilder             — assembles cohorts from filtered encounter records
├── problem_list_extractor.py            ProblemListExtractor             — extracts active problem list from encounter records
├── readmission_risk_scorer.py           ReadmissionRiskScorer            — scores 30-day readmission risk (LACE+ model)
├── rx_norm_mapper.py                    RxNormMapper                     — maps drug identifiers to RxNorm CUIs
├── snomed_hierarchy_expander.py         SnomedHierarchyExpander          — expands SNOMED CT concepts to descendant codes
├── social_determinants_extractor.py     SocialDeterminantsExtractor      — extracts SDOH factors from clinical notes
└── vitals_range_checker.py              VitalsRangeChecker               — validates vital signs against age/sex reference ranges
```

## Canonical pattern

HL7v2 decoded record → ICD-10 validate → NLP extract from note → cohort filter:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.hl7v2_message_parser import Hl7v2MessageParser
from pirn.domains.health.clinical.icd10_code_validator import Icd10CodeValidator
from pirn.domains.health.clinical.clinical_nlp_extractor import ClinicalNlpExtractor
from pirn.domains.health.clinical.patient_cohort_builder import PatientCohortBuilder
from pirn.tapestry import Tapestry

# hl7v2_record is already PHI-redacted by Hl7v2Format at the connector layer
with Tapestry() as t:
    hl7_record = Parameter("hl7_record", dict)
    note_text  = Parameter("note_text", str)

    parsed = Hl7v2MessageParser(
        record=hl7_record,
        _config=KnotConfig(id="parse"),
    )
    validated = Icd10CodeValidator(
        encounter=parsed,
        _config=KnotConfig(id="icd_validate"),
    )
    nlp_facts = ClinicalNlpExtractor(
        text=note_text,
        _config=KnotConfig(id="nlp"),
    )
    PatientCohortBuilder(
        encounter=validated,
        nlp_facts=nlp_facts,
        _config=KnotConfig(id="cohort"),
    )

result = await t.run(RunRequest(parameters={
    "hl7_record": decoded_hl7_dict,   # from Hl7v2Format.decode()
    "note_text": discharge_note,
}))
cohort = result.outputs["cohort"]
```

## Anti-patterns

**Feeding raw HL7v2 bytes directly to clinical knots** — HL7v2 bytes must pass through `Hl7v2Format.decode()` at the connector layer first; that decode step performs PHI redaction. Passing raw bytes to `Hl7v2MessageParser` skips redaction and will likely raise a `TypeError` since the knot expects a decoded `dict`.

**Calling `SnomedHierarchyExpander` without a loaded hierarchy** — `SnomedHierarchyExpander` requires an in-memory SNOMED CT RF2 release loaded at init time. Instantiating the knot without a valid release path will raise `RuntimeError` at the first `process()` call, not at wiring time. Provide the RF2 directory via `KnotConfig.extra`.

**Using `ReadmissionRiskScorer` as a clinical decision support tool** — the LACE+ model implemented here is a research-grade risk stratifier, not a clinically validated CDT. Its output is a float score suitable for retrospective cohort analysis. Do not surface the score directly in clinical workflows without independent validation and appropriate regulatory review.

## Constraints and gotchas

- `ClinicalNlpExtractor` and `SocialDeterminantsExtractor` load a spaCy model on first call; ensure `en_core_sci_lg` (or configured equivalent) is installed and accessible on the worker.
- `Icd10CodeValidator` ships a bundled ICD-10-CM code set. The bundled release year is fixed at package build time; update `pirn[clinical]` to get a newer release.
- `_dedup_rx_cuis.py` is an internal helper module, not a public knot. Do not import or wire it directly.
- `ClinicalDataQualityGate` raises `ClinicalDataQualityError` — catch it at the tapestry call site if partial cohort results are acceptable.
- `EncounterTimelineAssembler` sorts by encounter date; records missing a date field are placed at the end of the timeline with a warning emitted to the knot logger, not a raised exception.
- Install: `pip install pirn[clinical]`

## Quick reference

| Task | How |
|---|---|
| Parse HL7v2 decoded record | `Hl7v2MessageParser` |
| Validate diagnosis codes | `Icd10CodeValidator` |
| Map drug names to RxNorm | `MedicationStandardizer` → `RxNormMapper` |
| Expand SNOMED concept to descendants | `SnomedHierarchyExpander` |
| Extract NLP entities from notes | `NoteSectionSplitter` → `ClinicalNlpExtractor` |
| Extract SDOH from notes | `SocialDeterminantsExtractor` |
| Build patient cohort | `PatientCohortBuilder` with `ClinicalTrialEligibilityFilter` |
| Score readmission risk | `ReadmissionRiskScorer` on encounter record |
| Validate and normalise lab results | `LabResultNormalizer` after `ClinicalDataQualityGate` |
| Chronological encounter view | `EncounterTimelineAssembler` |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
