"""ML Engineering / Data Science knot library.

Install with::

    pip install 'pirn[ml]'

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

from pirn.domains.extras_loader import ExtrasLoader


ExtrasLoader("ml", ["numpy", "pandas", "sklearn"]).require()


__all__: list[str] = []
