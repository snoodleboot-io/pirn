"""``EegObjectStoreDisassembler`` — disassemble an EEG :class:`HealthSignalPayload` into bytes.

Thin subclass of
:class:`~pirn_health.disassemblers.mne_signal_object_store_disassembler.MneSignalObjectStoreDisassembler`
— see that module for the algorithm and references. This class exists to
give EEG-sourced payloads their own public, discoverable name and error
messages.
"""

from __future__ import annotations

from pirn_health.disassemblers.mne_signal_object_store_disassembler import (
    MneSignalObjectStoreDisassembler,
)


class EegObjectStoreDisassembler(MneSignalObjectStoreDisassembler):
    """Disassemble an EEG :class:`HealthSignalPayload` into raw bytes for object store upload."""
