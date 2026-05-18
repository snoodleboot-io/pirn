# Backlog: Reintegrate antspyx for advanced MRI operations

## Status
Deferred — antspyx removed 2026-05-18

## Background
antspyx was removed from `pirn[mri]` because it has a hard `numpy<2.4.0` constraint in its
published metadata, which conflicts with pirn's core `numpy>=2.4.4` requirement (needed for
cp314 wheels on Python 3.14). Universal resolution in uv applies this constraint even when
antspyx is gated by `python_version<'3.14'`.

The `scipy<1.16` constraint was removed upstream (antspyx main, ~Feb 2025) but has NOT yet
been released — latest release is 0.6.3 (Feb 2026) and still carries it.

## Current replacement
- `BrainMaskExtractor` → `dipy.segment.mask.median_otsu`
- `ImageRegistrar` → `SimpleITK.ImageRegistrationMethod`
- `MotionCorrector` → `dipy.align.imaffine.AffineRegistration` (rigid)

## When to revisit
Reintegrate antspyx when:
1. antspyx releases a version with `numpy>=2.4` (no upper cap)
2. AND releases a version with no `scipy` upper cap

At that point:
- Add `antspyx>=<new-version>; python_version<'3.14'` back to `mri` extra
- Consider restoring `ants`-based implementations as higher-fidelity alternatives
  (ANTs SyN is more accurate than SimpleITK BSpline for nonlinear registration)

## Files to update
- `pirn/domains/health/mri/brain_mask_extractor.py`
- `pirn/domains/health/mri/image_registrar.py`
- `pirn/domains/health/mri/motion_corrector.py`
- `pyproject.toml` (`mri` extra, `all-domains`, `all` inline lists)
