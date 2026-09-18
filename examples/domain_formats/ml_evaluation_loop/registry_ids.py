"""``RegistryIds`` — the well-known knot ids this example's outputs are read by.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from typing import ClassVar


class RegistryIds:
    """Knot ids shared by the decider that registers them and the driver."""

    complete: ClassVar[str] = "registry_complete"
