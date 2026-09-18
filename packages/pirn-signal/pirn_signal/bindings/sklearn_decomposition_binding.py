"""``SklearnDecompositionBinding`` — typed boundary over ``sklearn.decomposition``.

scikit-learn ships no type stubs; strict pyright reports its estimators as
partially unknown. This binding performs the lazy optional-extra import and
exposes the ``fit_transform`` of each estimator the separation knots use with
real ``NDArray`` annotations. Every method takes a sample matrix shaped
``(n_samples, n_features)`` and returns the transformed matrix shaped
``(n_samples, n_components)``, as scikit-learn does.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.optional_dependency import OptionalDependency


class SklearnDecompositionBinding:
    """Annotated facade over the ``sklearn.decomposition`` estimators used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> SklearnDecompositionBinding:
        """Import ``sklearn.decomposition`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``sklearn.decomposition`` is not installed; the message names
                ``pirn-signal[separation]``.
        """
        return cls(
            OptionalDependency.require(
                "sklearn.decomposition", extra="separation", package="pirn-signal"
            )
        )

    def fast_ica(
        self,
        samples: NDArray[np.floating[Any]],
        component_count: int,
        max_iterations: int,
        contrast: str = "logcosh",
    ) -> NDArray[np.float64]:
        """FastICA source estimates, with contrast function ``contrast`` and a fixed seed."""
        estimator: Any = self._module.FastICA(
            n_components=component_count, fun=contrast, max_iter=max_iterations, random_state=0
        )
        sources: NDArray[np.float64] = estimator.fit_transform(samples)
        return sources

    def nmf(
        self, samples: NDArray[np.floating[Any]], component_count: int, max_iterations: int
    ) -> NDArray[np.float64]:
        """Non-negative matrix factorisation activations ``W`` (``samples ~= W @ H``)."""
        estimator: Any = self._module.NMF(n_components=component_count, max_iter=max_iterations)
        activations: NDArray[np.float64] = estimator.fit_transform(samples)
        return activations

    def pca(
        self, samples: NDArray[np.floating[Any]], component_count: int, whiten: bool
    ) -> NDArray[np.float64]:
        """Principal-component scores, optionally whitened."""
        estimator: Any = self._module.PCA(n_components=component_count, whiten=whiten)
        scores: NDArray[np.float64] = estimator.fit_transform(samples)
        return scores

    def sparse_pca(
        self, samples: NDArray[np.floating[Any]], component_count: int, alpha: float
    ) -> NDArray[np.float64]:
        """Sparse-PCA scores with L1 penalty ``alpha`` and a fixed seed."""
        estimator: Any = self._module.SparsePCA(
            n_components=component_count, alpha=alpha, random_state=0
        )
        scores: NDArray[np.float64] = estimator.fit_transform(samples)
        return scores

    def dictionary_learning(
        self,
        samples: NDArray[np.floating[Any]],
        atom_count: int,
        alpha: float,
        max_iterations: int,
    ) -> NDArray[np.float64]:
        """Sparse codes of ``samples`` over a learned dictionary of ``atom_count`` atoms."""
        estimator: Any = self._module.DictionaryLearning(
            n_components=atom_count, alpha=alpha, max_iter=max_iterations, random_state=0
        )
        codes: NDArray[np.float64] = estimator.fit_transform(samples)
        return codes

    def pursuit_codes(
        self,
        samples: NDArray[np.floating[Any]],
        atom_count: int,
        alpha: float,
        max_iterations: int,
        transform_algorithm: str,
        transform_nonzero_coefficients: int | None,
    ) -> NDArray[np.float64]:
        """Sparse codes of ``samples`` coded by an explicit pursuit algorithm.

        ``DictionaryLearning.fit_transform`` returns the code the dictionary-learning
        loop produced, which never consults ``transform_algorithm``; the dictionary is
        therefore fitted first and the samples coded in a second ``transform`` call, so
        the requested pursuit is the one that runs.

        Args:
            samples: Sample matrix shaped ``(n_samples, n_features)``.
            atom_count: Number of dictionary atoms.
            alpha: Sparsity penalty while learning the dictionary, and the L1 penalty
                of the ``lasso_cd`` pursuit.
            max_iterations: Maximum dictionary-learning iterations.
            transform_algorithm: ``omp``, ``lars`` or ``lasso_cd``.
            transform_nonzero_coefficients: Maximum non-zeros per code for ``omp`` and
                ``lars``; ``None`` for ``lasso_cd``, which is driven by ``alpha``.

        Returns:
            The sparse codes, shaped ``(n_samples, atom_count)``.
        """
        estimator: Any = self._module.DictionaryLearning(
            n_components=atom_count,
            alpha=alpha,
            max_iter=max_iterations,
            transform_algorithm=transform_algorithm,
            transform_n_nonzero_coefs=transform_nonzero_coefficients,
            transform_alpha=alpha,
            random_state=0,
        )
        estimator.fit(samples)
        codes: NDArray[np.float64] = estimator.transform(samples)
        return codes

    def fast_ica_fit_subset(
        self,
        fit_samples: NDArray[np.floating[Any]],
        apply_samples: NDArray[np.floating[Any]],
        component_count: int,
        max_iterations: int,
        contrast: str = "logcosh",
    ) -> NDArray[np.float64]:
        """FastICA unmixing learned on ``fit_samples`` and applied to ``apply_samples``.

        Args:
            fit_samples: Samples the unmixing matrix is estimated from, shaped
                ``(n_fit_samples, n_features)``.
            apply_samples: Samples to unmix, shaped ``(n_samples, n_features)``.
            component_count: Number of independent components.
            max_iterations: FastICA iteration cap.
            contrast: FastICA contrast function.

        Returns:
            Source estimates for ``apply_samples``, shaped ``(n_samples, component_count)``.
        """
        estimator: Any = self._module.FastICA(
            n_components=component_count, fun=contrast, max_iter=max_iterations, random_state=0
        )
        estimator.fit(fit_samples)
        sources: NDArray[np.float64] = estimator.transform(apply_samples)
        return sources
