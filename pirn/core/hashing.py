"""Content-addressed hashing of values.

Lineage records reference values by hash, not by content.  Two runs that
produce the same value should produce the same hash, regardless of which
process / machine / Python session computed it.  We therefore use a
*canonical* serialisation: the same Python value always serialises to the
same bytes.

For Pydantic models we use the model's own JSON serialisation (deterministic
field order).  For everything else we recurse into containers and fall back
to ``repr`` for opaque types — repr is not perfectly stable across Python
versions, but it is stable within a deployment, which is the lineage scope
that matters in practice.

The hash is sha256 over the canonical bytes, encoded as hex.  Hex (not
base64) because hashes appear in logs and JSON often, where hex is the
universal-readable form.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence, Set
from typing import Any

from pydantic import BaseModel

# Sentinel for "value could not be hashed deterministically".  When emitted
# to a lineage record this still flows through; downstream tools that join
# on hashes will simply not match unhashable values to other runs.
UNHASHABLE = "unhashable"


def content_hash(value: Any) -> str:
    """Return a stable hex sha256 of ``value`` suitable for lineage joins.

    Stability rules
    ---------------
    * Pydantic models: hash of the model's JSON serialisation with sorted
      keys.  Two structurally identical models hash the same.
    * Mappings (dict): keys are sorted (lexicographic on str(key)) before
      serialisation.
    * Sequences (list, tuple): element order is preserved (it is part of
      the value).
    * Sets / frozensets: elements are hashed individually then sorted; the
      set hash is order-independent.
    * Primitives (str, int, float, bool, None): JSON-encoded.
    * Bytes: hex-encoded then JSON-wrapped (so they round-trip).
    * Anything else: ``repr(value)`` — best-effort.  Returns ``UNHASHABLE``
      prefix to signal the caller can't reliably compare across processes.
    """
    try:
        canonical = _canonicalise(value)
    except _Unhashable:
        return f"sha256:{UNHASHABLE}:{type(value).__name__}"
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


class _Unhashable(Exception):
    """Internal sentinel used by ``_canonicalise`` to bail on opaque values."""


def _canonicalise(value: Any) -> Any:
    """Recursively convert ``value`` into a JSON-serialisable canonical form.

    We use prefixed type tags ("__bytes__", "__set__", etc.) to ensure
    distinguishable hashes for values that would otherwise collide once
    serialised.  Without the tags, ``{"x": 1}`` and ``["x", 1]`` could in
    principle hash the same after JSON serialisation; with the tags they
    cannot.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, BaseModel):
        # Model JSON, then re-canonicalise the resulting dict so nested
        # non-Pydantic values are handled consistently.
        return {"__model__": value.__class__.__name__, "data": _canonicalise(
            value.model_dump(mode="json")
        )}
    if isinstance(value, Mapping):
        # Sort by str(key) for determinism.  Keys must serialise to strings
        # in JSON anyway.
        return {
            "__map__": [
                [_canonicalise(k), _canonicalise(value[k])]
                for k in sorted(value.keys(), key=str)
            ]
        }
    if isinstance(value, (set, frozenset, Set)):
        # Hash each element separately, then sort element-hashes for an
        # order-independent canonical form.
        element_hashes = sorted(content_hash(e) for e in value)
        return {"__set__": element_hashes}
    if isinstance(value, (list, tuple, Sequence)) and not isinstance(value, (str, bytes)):
        return {"__seq__": [_canonicalise(e) for e in value]}
    # Opaque type — bail.  Caller produces the UNHASHABLE marker.
    raise _Unhashable
