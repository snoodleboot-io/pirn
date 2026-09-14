"""``MegObjectStoreDisassembler`` — disassemble a MEG :class:`HealthSignalPayload` into bytes.

Thin subclass of
:class:`~pirn_health.disassemblers._mne_signal_object_store_disassembler._MneSignalObjectStoreDisassembler`
— see that module for the algorithm and references. This class exists to
give MEG-sourced payloads their own public, discoverable name and error
messages.
"""

from __future__ import annotations

from pirn_health.disassemblers._mne_signal_object_store_disassembler import (
    _MneSignalObjectStoreDisassembler,  # pyright: ignore[reportPrivateUsage]  # package-internal helper
)


class MegObjectStoreDisassembler(_MneSignalObjectStoreDisassembler):
    """Disassemble a MEG :class:`HealthSignalPayload` into raw bytes for object store upload."""
