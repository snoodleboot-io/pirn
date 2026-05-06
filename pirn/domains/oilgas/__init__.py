"""Oil & Gas knot library.

The orchestration knots ship as slim stubs that validate inputs and
return typed result values. Production deployments that read SEG-Y or
LAS payloads must install the optional extras::

    pip install 'pirn[oilgas]'

Without the extras the orchestration graph still imports, type-checks,
and unit-tests; only the knots that need the real SDKs at runtime fail.
"""

from __future__ import annotations

__all__: list[str] = []
