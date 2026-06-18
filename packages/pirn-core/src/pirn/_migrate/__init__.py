"""Import-compatibility codemod for the pirn monolith split (SCD-17).

When pirn was a monolith the six domains lived under ``pirn.domains.<x>``.
They are now standalone packages that import as ``pirn_<x>`` (for x in
signal, oilgas, data, ml, agents, health). This package ships a reusable,
idempotent, deterministic line-based rewriter that updates consumer source
from the old ``pirn.domains.<x>`` spellings to the new ``pirn_<x>`` ones.

It is exposed to end users as the ``pirn-migrate-imports`` console script
(see ``pirn._migrate.main``) and reused as the migration tool in SCD-23.
"""

from __future__ import annotations
