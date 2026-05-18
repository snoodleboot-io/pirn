"""``ImageRegistrar`` — rigid / affine / nonlinear image registration.

Uses SimpleITK for robust image registration without antspyx.

Algorithm:
    1. Receive moving_path, fixed_path, transform, and output_registered_path strings.
    2. Validate paths are non-empty and transform is one of rigid/affine/syn.
    3. Compute an optimal transform mapping the moving image to the fixed image.
    4. Apply the composite transform and write to output_registered_path.
    5. Return the output registered image path.


References:
    - Lowekamp et al. (2013) The Design of SimpleITK.
    - Yaniv et al. (2018) SimpleITK Image-Analysis Notebooks.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

try:
    import SimpleITK as sitk

    _HAS_SITK: bool = True
except ImportError:
    sitk = None  # type: ignore[assignment]
    _HAS_SITK = False


def _register(moving_path: str, fixed_path: str, transform: str, output_path: str) -> None:
    if not _HAS_SITK or sitk is None:
        raise ImportError(
            "SimpleITK is required for ImageRegistrar — install with: pip install 'pirn[mri]'"
        )
    fixed = sitk.ReadImage(fixed_path, sitk.sitkFloat32)
    moving = sitk.ReadImage(moving_path, sitk.sitkFloat32)

    registration = sitk.ImageRegistrationMethod()
    registration.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
    registration.SetOptimizerAsGradientDescent(
        learningRate=1.0,
        numberOfIterations=100,
        convergenceMinimumValue=1e-6,
        convergenceWindowSize=10,
    )
    registration.SetOptimizerScalesFromPhysicalShift()
    registration.SetShrinkFactorsPerLevel(shrinkFactors=[4, 2, 1])
    registration.SetSmoothingSigmasPerLevel(smoothingSigmas=[2, 1, 0])
    registration.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    registration.SetInterpolator(sitk.sitkLinear)

    if transform == "syn":
        initial_tx = sitk.CenteredTransformInitializer(
            fixed, moving, sitk.Euler3DTransform(), sitk.CenteredTransformInitializerFilter.GEOMETRY
        )
        registration.SetInitialTransform(
            sitk.BSplineTransformInitializer(
                fixed, transformDomainMeshSize=[8] * fixed.GetDimension()
            )
        )
    else:
        tx_cls = (
            sitk.Euler3DTransform()
            if transform == "rigid"
            else sitk.AffineTransform(fixed.GetDimension())
        )
        initial_tx = sitk.CenteredTransformInitializer(
            fixed, moving, tx_cls, sitk.CenteredTransformInitializerFilter.GEOMETRY
        )
        registration.SetInitialTransform(initial_tx, inPlace=False)

    final_tx = registration.Execute(fixed, moving)
    resampled = sitk.Resample(
        moving,
        fixed,
        final_tx,
        sitk.sitkLinear,
        0.0,
        moving.GetPixelID(),
    )
    sitk.WriteImage(resampled, output_path)


class ImageRegistrar(Knot):
    """Register a moving image to a fixed image."""

    def __init__(
        self,
        *,
        moving_path: Knot | str,
        fixed_path: Knot | str,
        transform: Knot | str,
        output_registered_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            moving_path=moving_path,
            fixed_path=fixed_path,
            transform=transform,
            output_registered_path=output_registered_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        moving_path: str,
        fixed_path: str,
        transform: str,
        output_registered_path: str,
        **_: Any,
    ) -> str:
        """Register the moving image to the fixed image using the configured transform and return the output path.

        Args:
            moving_path: Non-empty path to the moving (source) image.
            fixed_path: Non-empty path to the fixed (target/reference) image.
            transform: One of rigid, affine, syn.
            output_registered_path: Non-empty path for the registered output image.

        Returns:
            Path string for the registered output image file.

        Raises:
            ValueError: If any path is empty or transform is invalid.
        """
        for label, value in (
            ("moving_path", moving_path),
            ("fixed_path", fixed_path),
            ("output_registered_path", output_registered_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ImageRegistrar: {label} must be a non-empty string")
        if transform not in ("rigid", "affine", "syn"):
            raise ValueError("ImageRegistrar: transform must be one of rigid/affine/syn")
        await asyncio.to_thread(
            _register, moving_path, fixed_path, transform, output_registered_path
        )
        return output_registered_path
