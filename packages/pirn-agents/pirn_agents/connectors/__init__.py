"""Service & data connectors (PAE-F16 / PIR-30).

The fourth connector category: the async service/data substrate that the base
tools (F6) and durable sessions (F14) build on. Every connector holds live,
pooled backend state and is therefore an opaque value at the pirn IO boundary;
each lazily imports its backend through
:func:`~pirn_agents._require._require`, so importing this package never imports
``httpx``, ``aiosqlite``, ``asyncpg``, ``aioboto3`` or any other backend.
"""

from __future__ import annotations
