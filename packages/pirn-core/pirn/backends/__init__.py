"""Backend implementations for pirn.

Interface base classes live in ``pirn.backends.base``: :class:`TapestryStore`
(the canonical knot definitions), :class:`RunHistory` (lineage records and run
summaries) and :class:`DataStore` (intermediate values, keyed by content hash).
They are three *independent* roles — a module below implements only the ones
listed against it, and a backend that fills one role does not thereby fill the
others.

===========================  ===============  ============  ===============
Module                       TapestryStore    RunHistory    DataStore
===========================  ===============  ============  ===============
``pirn.backends.in_memory``  yes              yes           yes
``pirn.backends.sqlite``     yes              yes           --
``pirn.backends.postgres``   yes              yes           --
``pirn.backends.valkey``     yes              --            yes
``pirn.backends.duckdb_history``     --               yes           --
``pirn.backends.local_disk_data_store``       --               --            yes
``pirn.backends.s3_data_store``         --               --            yes
``pirn.backends.gcs_data_store``        --               --            yes
``pirn.backends.azure_blob_data_store``      --               --            yes
===========================  ===============  ============  ===============

``--`` means no such class exists.  Notably ``SQLiteStore`` and
``PostgresStore`` are ``TapestryStore`` implementations; there is no
``SQLiteDataStore`` or ``PostgresDataStore``, so a SQLite- or Postgres-backed
tapestry still needs one of the data stores above.
"""
