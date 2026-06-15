Preprocesses and analyses MRI data — skull stripping, bias field correction, atlas registration, segmentation, tractography, and functional connectivity — does NOT read DICOM or NIfTI files; use DicomFormat or NiftiFormat from the file_formats connector layer for I/O.

## Mental model

MRI knots operate on in-memory image arrays or file paths produced by a preceding format-connector decode step. The standard preprocessing chain is: skull strip → bias correct → intensity normalise → register to atlas. Analysis knots (segmentation, tractography, connectivity) expect a preprocessed image and will produce degraded results if called on raw scanner output.

Every knot that calls FSL, FreeSurfer, ANTs, or MRtrix does so via subprocess — the tool binary must be on PATH on the executing worker. Knots that use only Python libraries (nibabel, nilearn, scikit-image) have no external binary dependency beyond `pip install pirn[mri]`.

The `MriQcGate` knot validates SNR, motion parameters, and field-of-view coverage. It raises `MriQcError` on failure so that non-diagnostic images are rejected before any analysis knot consumes them.

## Source map

```
pirn_health/mri/
├── atlas_aligner.py                          AtlasAligner                       — registers image to standard atlas space (MNI/Talairach)
├── bias_field_corrector.py                   BiasFieldCorrector                 — N4 bias field correction via ANTs
├── bids_converter.py                         BidsConverter                      — converts NIfTI + metadata to BIDS directory structure
├── brain_age_estimator.py                    BrainAgeEstimator                  — predicts brain age from structural MRI features
├── brain_mask_extractor.py                   BrainMaskExtractor                 — extracts binary brain mask from T1w volume
├── cortical_thickness_estimator.py           CorticalThicknessEstimator         — estimates regional cortical thickness via FreeSurfer
├── dti_preprocessor.py                       DtiPreprocessor                    — eddy current correction and tensor fitting for DTI
├── functional_connectivity_extractor.py      FunctionalConnectivityExtractor    — extracts ROI-to-ROI connectivity matrices from fMRI
├── image_registrar.py                        ImageRegistrar                     — pairwise image registration (rigid/affine/deformable)
├── intensity_normalizer.py                   IntensityNormalizer                — intensity normalisation across subjects/sessions
├── lesion_segmenter.py                       LesionSegmenter                    — white matter and focal lesion segmentation
├── mri_qc_gate.py                            MriQcGate                          — quality gate; raises MriQcError on SNR/motion failure
├── resting_state_extractor.py                RestingStateExtractor              — nuisance regression and band-pass filtering for rs-fMRI
├── skull_stripper.py                         SkullStripper                      — removes non-brain tissue via BET/HD-BET
├── spatial_smoother.py                       SpatialSmoother                    — Gaussian spatial smoothing (FWHM configurable)
├── surface_reconstructor.py                  SurfaceReconstructor               — cortical surface reconstruction via FreeSurfer recon-all
├── tractography_runner.py                    TractographyRunner                 — probabilistic tractography via MRtrix3
├── tumor_segmenter.py                        TumorSegmenter                     — glioma segmentation (BraTS model)
├── vbm_processor.py                          VbmProcessor                       — voxel-based morphometry preprocessing pipeline
├── white_matter_hyperintensity_segmenter.py  WhiteMatterHyperintensitySegmenter — WMH segmentation via LST/deep-learning model
└── wmh_volume_quantifier.py                  WmhVolumeQuantifier                — quantifies WMH volume from segmentation mask
```

## Canonical pattern

NIfTI bytes → skull strip → bias correct → atlas align → lesion segment:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn_health.mri.skull_stripper import SkullStripper
from pirn_health.mri.bias_field_corrector import BiasFieldCorrector
from pirn_health.mri.atlas_aligner import AtlasAligner
from pirn_health.mri.lesion_segmenter import LesionSegmenter
from pirn_health.mri.mri_qc_gate import MriQcGate
from pirn.tapestry import Tapestry

# nifti_bytes produced by NiftiFormat.decode() upstream
with Tapestry() as t:
    nifti_bytes = Parameter("nifti_bytes", bytes)

    qc = MriQcGate(
        image=nifti_bytes,
        _config=KnotConfig(id="qc"),
    )
    stripped = SkullStripper(
        image=nifti_bytes,
        qc_pass=qc,
        _config=KnotConfig(id="skull_strip"),
    )
    corrected = BiasFieldCorrector(
        image=stripped,
        _config=KnotConfig(id="bias_correct"),
    )
    registered = AtlasAligner(
        image=corrected,
        _config=KnotConfig(id="atlas_align"),
    )
    LesionSegmenter(
        image=registered,
        _config=KnotConfig(id="lesion_seg"),
    )

result = await t.run(RunRequest(parameters={
    "nifti_bytes": open("sub-01_T1w.nii.gz", "rb").read(),
}))
lesion_mask = result.outputs["lesion_seg"]
```

## Anti-patterns

**Running analysis knots on raw scanner output** — knots like `LesionSegmenter`, `TumorSegmenter`, and `FunctionalConnectivityExtractor` are validated against preprocessed, skull-stripped, bias-corrected images in standard space. Passing raw NIfTI output from the scanner will produce silently wrong results, not errors.

**Wiring `TractographyRunner` without DTI preprocessing** — `TractographyRunner` expects a fitted tensor or fibre orientation distribution, not a raw DWI volume. Wire `DtiPreprocessor` before `TractographyRunner`; skipping it will cause MRtrix3 to fail with an opaque input-format error.

**Reusing atlas-space paths across workers** — `AtlasAligner` and `ImageRegistrar` write intermediate warp fields to a temporary directory on the executing worker. Do not share or cache these paths across tapestry runs or distributed workers; each run creates its own scratch space.

## Constraints and gotchas

- Binary dependencies by knot: `SkullStripper` requires FSL `bet` or HD-BET; `BiasFieldCorrector` requires ANTs `N4BiasFieldCorrection`; `SurfaceReconstructor` and `CorticalThicknessEstimator` require FreeSurfer; `TractographyRunner` requires MRtrix3.
- `NiftiFormat` writes to a temp file internally — ensure `/tmp` is writable and has sufficient space for the volumes being processed (up to several GB for high-res T1w or DWI).
- `SurfaceReconstructor` wraps `recon-all`, which takes 6–12 hours per subject. Run it on a dedicated worker with a long timeout configured in `KnotConfig.extra`.
- `MriQcGate` raises `MriQcError` (not a subclass of the health-domain base error). Catch it specifically at the tapestry call site.
- `BidsConverter` produces a directory tree on the local filesystem, not in-memory bytes. The output value is a path string.
- Install: `pip install pirn[mri]`

## Quick reference

| Task | How |
|---|---|
| Decode NIfTI/DICOM bytes | `NiftiFormat.decode()` or `DicomFormat.decode()` (connector layer) |
| Skull strip T1w | `MriQcGate` → `SkullStripper` |
| Bias field correction | `BiasFieldCorrector` (requires ANTs) |
| Register to MNI space | `AtlasAligner` or `ImageRegistrar` |
| Cortical thickness | `SkullStripper` → `BiasFieldCorrector` → `SurfaceReconstructor` → `CorticalThicknessEstimator` |
| WMH detection and volume | `WhiteMatterHyperintensitySegmenter` → `WmhVolumeQuantifier` |
| Glioma segmentation | `TumorSegmenter` on FLAIR/T1ce/T2 registered stack |
| rs-fMRI connectivity | `RestingStateExtractor` → `FunctionalConnectivityExtractor` |
| DTI tractography | `DtiPreprocessor` → `TractographyRunner` |
| VBM analysis | `VbmProcessor` (wraps full SPM/FSL VBM pipeline) |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
