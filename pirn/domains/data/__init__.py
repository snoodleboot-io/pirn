"""Data Engineering / Analytics Engineering knot library.

Install with::

    pip install 'pirn[data]'

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

from pirn.domains._extras import require_extra

require_extra("data", ["pandas", "pyarrow"])

# Knot modules are imported once they exist; KnotRegistry registration happens
# inside each module. Add imports here as they land:
#
# from pirn.domains.data import sources, transforms, quality, sinks  # noqa: F401

__all__: list[str] = []
