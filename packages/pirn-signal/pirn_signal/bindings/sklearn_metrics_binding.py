"""``SklearnMetricsBinding`` — typed boundary over ``sklearn.metrics``.

scikit-learn ships no type stubs. This binding performs the lazy optional-extra
import and exposes the clustering-quality metric the audio knots use with a real
return annotation.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.optional_dependency import OptionalDependency


class SklearnMetricsBinding:
    """Annotated facade over the ``sklearn.metrics`` functions used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> SklearnMetricsBinding:
        """Import ``sklearn.metrics`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``sklearn.metrics`` is not installed; the message names
                ``pirn-signal[separation]``.
        """
        return cls(
            OptionalDependency.require("sklearn.metrics", extra="separation", package="pirn-signal")
        )

    def silhouette(self, samples: NDArray[np.floating[Any]], labels: NDArray[np.int_]) -> float:
        """Mean silhouette coefficient of ``labels`` over ``samples``, in ``[-1, 1]``.

        Args:
            samples: Feature matrix shaped ``(n_samples, n_features)``.
            labels: Cluster label per sample; at least two distinct labels, and
                fewer labels than samples (scikit-learn's requirement).

        Returns:
            The mean silhouette coefficient — higher is a better-separated clustering.
        """
        score: float = float(self._module.silhouette_score(samples, labels))
        return score
