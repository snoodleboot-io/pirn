"""Digital Signal Processing knot library.

Install with::

    pip install 'pirn[signal]'

The core orchestration layer (types and the slim ``Knot`` stubs under
``spectral``, ``filters``, ``wavelets``, ``adaptive``, ``statistical``,
``separation``, ``nonlinear``, ``resampling``, ``audio``) is pure-Python
and importable without ``scipy`` / ``pywavelets`` / ``librosa``. Concrete
DSP backends will instantiate
:class:`pirn.domains.extras_loader.ExtrasLoader` at the call boundary so
the missing-extras error fires only when a real implementation is used.
"""

# Pure-Python orchestration layer; no module-level dependencies on
# scipy, pywavelets, or librosa. See module docstring above.

__all__: list[str] = []
