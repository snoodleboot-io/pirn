"""Compression codec implementations used by ``CompressedFileFormat``.

One class per file. Each codec implements
:class:`pirn.domains.connectors.file_formats.codec.Codec` and is
imported lazily by ``CompressedFileFormat._load_codec`` so optional
SDK dependencies are not pulled in unless the user opts into the
relevant extra (``pirn[zstd]``, ``pirn[snappy]``, ``pirn[lz4]``).
"""
