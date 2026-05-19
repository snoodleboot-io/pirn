Processes clinical trial data — CDISC SDTM/ADaM dataset construction, regulatory submission artefacts, survival analysis, and real-world evidence cohort extraction — does NOT interface with EDC systems; ingest trial data via DatabaseQuerySource.

## Mental model

Trials knots map raw clinical data through the CDISC data model. The standard flow is raw EDC data → SDTM domain validation → ADaM dataset construction → statistical analysis. Regulatory artefacts (Define-XML) are generated as a final output step, not as an intermediate; wire `DefineXmlGenerator` last.

`SdtmDomainValidator` and `MeddraNormalizer` are gatekeepers. `SdtmDomainValidator` raises `ValueError` when a domain's column set or controlled-terminology values violate CDISC SDTM Implementation Guide rules. `MeddraNormalizer` requires a licensed MedDRA release loaded at init time; it will not substitute or approximate unmapped terms.

Real-world evidence (`RweCohortExtractor`) and randomised trial analysis (`RandomizedTrialAnalyzer`) are separate knots precisely because their statistical assumptions differ. Do not share a `PatientCohortBuilder` output between them without explicit covariate adjustment.

## Source map

```
pirn/domains/health/trials/
├── adam_dataset_builder.py                   AdamDatasetBuilder              — constructs CDISC ADaM analysis datasets (ADSL, ADAE, ADTTE, etc.)
├── clinical_event_aggregator.py              ClinicalEventAggregator         — aggregates AEs, concomitant meds, and procedures per subject
├── define_xml_generator.py                   DefineXmlGenerator              — generates CDISC Define-XML 2.0 submission metadata
├── estimand_aligned_analyzer.py              EstimandAlignedAnalyzer         — applies ICH E9(R1) estimand framework to primary endpoint analysis
├── meddra_normalizer.py                      MeddraNormalizer                — maps verbatim adverse event terms to MedDRA PT/HLT/SOC hierarchy
├── propensity_score_matcher_pipeline.py      PropensityScoreMatcherPipeline  — propensity score matching/weighting for observational studies
├── randomized_trial_analyzer.py              RandomizedTrialAnalyzer         — ITT/PP/mITT analysis with multiplicity adjustment
├── rwe_cohort_extractor.py                   RweCohortExtractor              — extracts and characterises real-world evidence cohorts
├── sdtm_domain_validator.py                  SdtmDomainValidator             — validates SDTM datasets against CDISC IG and CT
└── survival_analysis_pipeline.py             SurvivalAnalysisPipeline        — Kaplan-Meier, Cox PH, and competing-risks survival analysis
```

## Canonical pattern

Raw trial data → SDTM validate → ADaM build → survival analysis:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.sdtm_domain_validator import SdtmDomainValidator
from pirn.domains.health.trials.adam_dataset_builder import AdamDatasetBuilder
from pirn.domains.health.trials.meddra_normalizer import MeddraNormalizer
from pirn.domains.health.trials.survival_analysis_pipeline import SurvivalAnalysisPipeline
from pirn.tapestry import Tapestry

with Tapestry() as t:
    sdtm_ds  = Parameter("sdtm_ds", dict)   # DS domain records (dict of domain → DataFrame)
    sdtm_ae  = Parameter("sdtm_ae", dict)   # AE domain records
    sdtm_adsl = Parameter("sdtm_adsl", dict) # ADSL source rows

    validated_ds = SdtmDomainValidator(
        domain="DS",
        records=sdtm_ds,
        _config=KnotConfig(id="validate_ds"),
    )
    normalised_ae = MeddraNormalizer(
        ae_records=sdtm_ae,
        _config=KnotConfig(id="meddra"),
    )
    adtte = AdamDatasetBuilder(
        dataset="ADTTE",
        ds=validated_ds,
        ae=normalised_ae,
        adsl=sdtm_adsl,
        _config=KnotConfig(id="adtte"),
    )
    SurvivalAnalysisPipeline(
        adtte=adtte,
        endpoint="OS",
        _config=KnotConfig(id="km_os"),
    )

result = await t.run(RunRequest(parameters={
    "sdtm_ds": ds_domain_dict,
    "sdtm_ae": ae_domain_dict,
    "sdtm_adsl": adsl_rows_dict,
}))
km_results = result.outputs["km_os"]
```

## Anti-patterns

**Generating Define-XML before SDTM validation** — `DefineXmlGenerator` derives its ItemDef metadata from the actual column set of your SDTM datasets. Generating Define-XML from unvalidated data embeds non-compliant column names into the submission package. Always run `SdtmDomainValidator` before `DefineXmlGenerator`.

**Using `RandomizedTrialAnalyzer` on observational data** — `RandomizedTrialAnalyzer` assumes treatment assignment is random and applies ITT/PP population logic accordingly. Applying it to observational or RWE data without prior propensity score adjustment will produce biased treatment-effect estimates. Use `PropensityScoreMatcherPipeline` followed by `RweCohortExtractor` for non-randomised data.

**Loading MeddraNormalizer without a licensed release** — `MeddraNormalizer` requires a valid, locally stored MedDRA release directory provided via `KnotConfig.extra`. It does not fall back to approximate matching or public code lists. Instantiating it without a valid release path raises `RuntimeError` at the first `process()` call.

## Constraints and gotchas

- MedDRA is a licensed terminology. You must hold a valid MedDRA licence and provide the release directory path; pirn does not bundle or distribute MedDRA content.
- `SurvivalAnalysisPipeline` uses `lifelines` for Kaplan-Meier and Cox PH, and `pymsm` for competing risks. Both are included in `pirn[trials]`; do not pin them separately as version conflicts can occur.
- `EstimandAlignedAnalyzer` implements ICH E9(R1) strategies (treatment policy, hypothetical, composite, while on treatment, principal stratum). The estimand strategy must be specified in `KnotConfig.extra`; the default is treatment-policy.
- `AdamDatasetBuilder` supports ADSL, ADAE, ADTTE, ADCM, and ADLB dataset types. Requesting an unsupported dataset type raises `NotImplementedError`.
- `DefineXmlGenerator` output is an XML bytes object conforming to CDISC Define-XML 2.0. Write it to disk before submission; do not pass it as input to other knots.
- Install: `pip install pirn[trials]`

## Quick reference

| Task | How |
|---|---|
| Validate SDTM domain | `SdtmDomainValidator` (one knot per domain) |
| Normalise AE verbatim terms | `MeddraNormalizer` |
| Build ADaM analysis dataset | `AdamDatasetBuilder` (specify dataset type in config) |
| Generate Define-XML | `DefineXmlGenerator` on validated SDTM datasets |
| Survival analysis | `SurvivalAnalysisPipeline` on ADTTE |
| ITT/PP efficacy analysis | `RandomizedTrialAnalyzer` |
| Estimand-aligned analysis | `EstimandAlignedAnalyzer` |
| Propensity score matching | `PropensityScoreMatcherPipeline` |
| RWE cohort | `RweCohortExtractor` → `PropensityScoreMatcherPipeline` |
| Aggregate AEs/conmeds | `ClinicalEventAggregator` |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
