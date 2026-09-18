"""``LayerProfiler`` — derives params, memory and FLOPs from tensor shapes.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.ml_evaluation_loop.layer_profile import LayerProfile
from examples.domain_formats.ml_evaluation_loop.model_artifact import ModelArtifact


class LayerProfiler(Knot):
    """Analyse tensor shapes to count params, estimate memory and FLOPs."""

    _dtype_bytes: ClassVar[dict[str, int]] = {
        "float32": 4,
        "float16": 2,
        "bfloat16": 2,
        "int8": 1,
    }

    async def process(self, artifact: ModelArtifact, **_: Any) -> LayerProfile:
        total_params = 0
        layer_count = len(artifact.tensors)
        compute_ops = 0

        for _name, tensor in artifact.tensors.items():
            shape = tensor["shape"]
            n_elements = math.prod(shape) if shape else 1
            total_params += n_elements
            # Estimate FLOPs: 2 multiplications per parameter for matmul-like ops
            if len(shape) >= 2:
                compute_ops += 2 * n_elements

        # Use float32 as fallback; sample from first tensor's dtype
        sample_dtype = "float32"
        if artifact.tensors:
            sample_dtype = next(iter(artifact.tensors.values())).get("dtype", "float32")
        bytes_per_param = self._dtype_bytes.get(sample_dtype, 4)
        memory_mb = (total_params * bytes_per_param) / (1024 * 1024)

        return LayerProfile(
            model_id=artifact.model_id,
            total_params=total_params,
            layer_count=layer_count,
            memory_mb=memory_mb,
            compute_ops_per_sample=compute_ops,
        )
