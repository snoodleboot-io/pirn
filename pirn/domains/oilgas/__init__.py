"""Oil & Gas knot library.

Install with::

    pip install 'pirn[oilgas]'

Covers seismic (SEG-Y), well/petrophysics (LAS), reservoir engineering
(ECLIPSE/CMG), production operations (SCADA/PRODML), facilities integrity,
and geospatial. See ``planning/current/domain-knot-libraries-prd.md`` for the
full catalog.
"""

from pirn.domains._extras import require_extra

require_extra("oilgas", ["segyio", "lasio"])

__all__: list[str] = []
