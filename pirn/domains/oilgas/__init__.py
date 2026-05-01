"""Oil & Gas knot library.

Install with::

    pip install 'pirn[oilgas]'
"""

from pirn.domains.extras_loader import ExtrasLoader


ExtrasLoader("oilgas", ["segyio", "lasio"]).require()


__all__: list[str] = []
