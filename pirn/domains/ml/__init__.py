"""ML Engineering / Data Science knot library.

Install with::

    pip install 'pirn[ml]'

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

from pirn.domains._extras import require_extra

require_extra("ml", ["numpy", "pandas", "sklearn"])

__all__: list[str] = []
