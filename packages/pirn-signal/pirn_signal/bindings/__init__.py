"""Typed boundaries over the untyped third-party DSP libraries.

scipy, PyWavelets, EMD-signal, vmdpy, scikit-learn and soundfile ship no type
stubs, so strict pyright sees every direct call into them as partially unknown.
Each binding class here obtains its module lazily through
:class:`pirn_signal.signal_optional_dependency.SignalOptionalDependency` (which
keeps ``import pirn_signal`` free of heavy dependencies and raises the
optional-extra ``ImportError``), and exposes the calls the knots use as fully
annotated methods that convert every value read off the module to a precise
type immediately. Knots depend on a binding, never on the untyped module
directly. Each binding is imported from its own concrete module; this package
does not re-export them.
"""
