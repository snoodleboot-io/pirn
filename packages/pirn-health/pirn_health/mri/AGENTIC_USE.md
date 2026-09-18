Preprocesses and analyses MRI data — brain masking, bias field correction, atlas registration, segmentation, diffusion and functional connectivity — does NOT read DICOM or NIfTI files into memory; use DicomFormat or NiftiFormat from the file_formats connector layer for I/O.

## Mental model

Most MRI knots operate on NIfTI file paths: each takes an input path and an output path and returns the output path, so a preprocessing chain is wired by feeding one knot's return value into the next knot's `nifti_path`. The standard preprocessing chain is: brain mask → bias correct → intensity normalise → register to atlas. Analysis knots (segmentation, volumetrics, connectivity) expect a preprocessed image and will produce degraded results if called on raw scanner output.

Knots that shell out to ANTs, FreeSurfer, or nnU-Net need the tool binary on PATH on the executing worker. Knots that use only Python libraries (SimpleITK, dipy, nibabel) need only `pip install "pirn-health[mri]"`.

Several knots are marked `_is_stub = True` (`AtlasAligner`, `BiasFieldCorrector`, `IntensityNormalizer`, `CorticalThicknessEstimator`, `LesionSegmenter`, `RadiomicsExtractor`, `VolumetricAnalyzer`): they are wired and testable end-to-end but are not production-quality algorithms.

`MRIQualityController` computes SNR, CNR, and mean framewise displacement and returns a dict with `passes_qc` and `qc_flags`; it does not raise on a failing scan, so branch on `passes_qc` downstream.

## Source map

```
pirn_health/mri/
├── atlas_aligner.py                      AtlasAligner                    — registers image to a named atlas (MNI152) via ANTs
├── bias_field_corrector.py               BiasFieldCorrector              — N4 bias field correction via SimpleITK
├── bids_converter.py                     BIDSConverter                   — converts DICOM or NIfTI files to BIDS format
├── brain_age_estimator.py                BrainAgeEstimator               — predicts brain age from structural MRI features
├── brain_mask_extractor.py               BrainMaskExtractor              — skull-strips a T1w volume into a binary brain mask (dipy)
├── cortical_thickness_estimator.py       CorticalThicknessEstimator      — per-region cortical thickness via FreeSurfer recon-all
├── dti_preprocessor.py                   DTIPreprocessor                 — denoise, eddy correction and brain extraction for DTI
├── functional_connectivity_extractor.py  FunctionalConnectivityExtractor — connectivity matrix from resting-state fMRI
├── image_registrar.py                    ImageRegistrar                  — rigid / affine / nonlinear image registration
├── intensity_normalizer.py               IntensityNormalizer             — z-score / WhiteStripe intensity normalisation
├── lesion_segmenter.py                   LesionSegmenter                 — lesion segmentation via nnU-Net inference
├── motion_corrector.py                   MotionCorrector                 — rigid-body motion correction
├── mri_quality_controller.py             MRIQualityController            — SNR/CNR/motion QC metrics with a pass/fail flag
├── nifti_converter.py                    NIfTIConverter                  — converts a DICOM series to NIfTI
├── radiomics_extractor.py                RadiomicsExtractor              — pyradiomics-style radiomic features
├── region_of_interest_extractor.py       RegionOfInterestExtractor       — per-ROI statistics
├── spatial_normalizer.py                 SpatialNormalizer               — registers subject MRI to a standard atlas space
├── task_fmri_modeler.py                  TaskFMRIModeler                 — first-level GLM for task fMRI
├── vbm_morphometry_analyzer.py           VBMMorphometryAnalyzer          — voxel-based morphometry analysis
├── volumetric_analyzer.py                VolumetricAnalyzer              — per-region volume estimates
└── white_matter_analyzer.py              WhiteMatterAnalyzer             — white-matter integrity (FA / MD)
```

## Canonical pattern

NIfTI path → brain mask → bias correct → atlas align → lesion segment:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_health.mri.atlas_aligner import AtlasAligner
from pirn_health.mri.bias_field_corrector import BiasFieldCorrector
from pirn_health.mri.brain_mask_extractor import BrainMaskExtractor
from pirn_health.mri.lesion_segmenter import LesionSegmenter

with Tapestry() as t:
    t1w_path = Parameter("t1w_path", str)

    mask = BrainMaskExtractor(
        nifti_path=t1w_path,
        output_mask_path="work/sub-01_mask.nii.gz",
        _config=KnotConfig(id="brain_mask"),
    )
    corrected = BiasFieldCorrector(
        nifti_path=t1w_path,
        output_nifti_path="work/sub-01_n4.nii.gz",
        _config=KnotConfig(id="bias_correct"),
    )
    registered = AtlasAligner(
        nifti_path=corrected,
        atlas_name="MNI152",
        output_aligned_path="work/sub-01_mni.nii.gz",
        _config=KnotConfig(id="atlas_align"),
    )
    LesionSegmenter(
        nifti_path=registered,
        model_name="lesion_flair",
        output_segmentation_path="work/sub-01_lesions.nii.gz",
        _config=KnotConfig(id="lesion_seg"),
    )

result = await t.run(RunRequest(parameters={"t1w_path": "sub-01_T1w.nii.gz"}))
lesion_mask_path = result.outputs["lesion_seg"]
```

## Anti-patterns

**Running analysis knots on raw scanner output** — knots like `LesionSegmenter`, `VolumetricAnalyzer`, and `FunctionalConnectivityExtractor` assume preprocessed, skull-stripped, bias-corrected images in standard space. Passing raw NIfTI output from the scanner produces silently wrong results, not errors.

**Wiring `WhiteMatterAnalyzer` without DTI preprocessing** — FA/MD analysis expects denoised, eddy-corrected diffusion data. Wire `DTIPreprocessor` first.

**Reusing output paths across runs** — path-based knots write to the output path you give them. Do not share the same output paths across concurrent tapestry runs or distributed workers; parameterise them per subject/run.

## Constraints and gotchas

- Binary dependencies by knot: `AtlasAligner` requires ANTs (`antsRegistrationSyNQuick.sh`); `CorticalThicknessEstimator` requires FreeSurfer (`recon-all`); `LesionSegmenter` requires nnU-Net (`nnUNet_predict`).
- `NiftiFormat` writes to a temp file internally — ensure the temp directory is writable and has space for the volumes being processed (up to several GB for high-res T1w or DWI).
- `recon-all` takes many hours per subject. Run `CorticalThicknessEstimator` on a dedicated worker and set `KnotConfig(timeout=...)` accordingly.
- `MRIQualityController` raises `NotImplementedError` when `mri_data` carries no `voxel_data`; it does not load images from `nifti_path` itself.
- `BIDSConverter` produces a directory tree on the local filesystem, not in-memory bytes.
- Install: `pip install "pirn-health[mri]"`

## Quick reference

| Task | How |
|---|---|
| Decode NIfTI/DICOM bytes | `NiftiFormat` or `DicomFormat` (connector layer) |
| Convert DICOM series to NIfTI | `NIfTIConverter` |
| Scan quality check | `MRIQualityController` → branch on `passes_qc` |
| Skull strip T1w | `BrainMaskExtractor` |
| Bias field correction | `BiasFieldCorrector` |
| Register to MNI space | `AtlasAligner`, `SpatialNormalizer`, or `ImageRegistrar` |
| Cortical thickness | `BrainMaskExtractor` → `BiasFieldCorrector` → `CorticalThicknessEstimator` (requires FreeSurfer) |
| Lesion segmentation and volume | `LesionSegmenter` → `VolumetricAnalyzer` |
| rs-fMRI connectivity | `MotionCorrector` → `FunctionalConnectivityExtractor` |
| DTI white-matter metrics | `DTIPreprocessor` → `WhiteMatterAnalyzer` |
| VBM analysis | `VBMMorphometryAnalyzer` |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
