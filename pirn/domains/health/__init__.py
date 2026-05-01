"""Healthcare / Genomics / Imaging / EEG/MEG / Wearables / Pathology / Trials.

Install with::

    pip install 'pirn[health]'

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog
across the seven modalities.
"""

from pirn.domains._extras import require_extra

require_extra(
    "health",
    [
        "pydicom",            # DICOM medical imaging
        "mne",                # EEG / MEG processing
        "nibabel",            # NIfTI / neuroimaging
        "pyfaidx",            # FASTA / genomics
    ],
)

__all__: list[str] = []
