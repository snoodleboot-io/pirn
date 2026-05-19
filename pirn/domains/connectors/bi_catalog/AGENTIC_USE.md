`pirn.domains.connectors.bi_catalog` provides API clients for data catalog and integration platforms (dbt, Fivetran, Airbyte, DataHub, Alation, OpenMetadata) — it does not run dbt models or trigger syncs inline; it exposes their REST APIs so pipeline knots can read metadata, trigger runs, and publish lineage.

---

## Mental model

Each integration has a `*Config` (API credentials, base URL) and a `*Client` (thin async REST wrapper). Clients are `PirnOpaqueValue` — create once, pass as config constants to knots. The primary use cases are: reading column/table metadata to drive downstream processing, triggering sync jobs as pipeline steps, and publishing lineage events back to a catalog.

`dbt_artifacts_config.py` and `dbt_artifacts_reader.py` are special — they read local dbt artifact JSON files (manifest.json, catalog.json) rather than calling a remote API.

---

## Source map

```
pirn/domains/connectors/bi_catalog/
├── dbt_artifacts_config.py   DbtArtifactsConfig   — manifest_path, catalog_path (local file paths)
├── dbt_artifacts_reader.py   DbtArtifactsReader   — reads dbt manifest.json / catalog.json
├── fivetran_config.py        FivetranConfig        — api_key, api_secret
├── fivetran_client.py        FivetranClient        — Fivetran REST API (connectors, sync status)
├── airbyte_config.py         AirbyteConfig         — base_url, client_id, client_secret
├── airbyte_client.py         AirbyteClient         — Airbyte API v1 (connections, jobs, streams)
├── datahub_config.py         DatahubConfig         — server (GMS URL), token
├── datahub_client.py         DatahubClient         — DataHub REST emitter + search API
├── alation_config.py         AlationConfig         — base_url, api_token
├── alation_client.py         AlationClient         — Alation REST API (schemas, articles, queries)
├── open_metadata_config.py   OpenMetadataConfig    — host_port, jwt_token
└── open_metadata_client.py   OpenMetadataClient    — OpenMetadata REST API (tables, lineage, tags)
```

---

## Canonical pattern

### Read dbt manifest for column metadata

```python
from pirn.domains.connectors.bi_catalog.dbt_artifacts_config import DbtArtifactsConfig
from pirn.domains.connectors.bi_catalog.dbt_artifacts_reader import DbtArtifactsReader

reader = DbtArtifactsReader(config=DbtArtifactsConfig(
    manifest_path="target/manifest.json",
    catalog_path="target/catalog.json",
))
schema = reader.get_model_schema("my_model")
```

### Trigger a Fivetran sync and wait

```python
from pirn.domains.connectors.bi_catalog.fivetran_config import FivetranConfig
from pirn.domains.connectors.bi_catalog.fivetran_client import FivetranClient

ft = FivetranClient(config=FivetranConfig(
    api_key=os.environ["FIVETRAN_KEY"],
    api_secret=os.environ["FIVETRAN_SECRET"],
))
# await ft.trigger_sync(connector_id="abc123")
# await ft.wait_for_sync(connector_id="abc123", timeout=600)
```

### Publish lineage to DataHub

```python
from pirn.domains.connectors.bi_catalog.datahub_config import DatahubConfig
from pirn.domains.connectors.bi_catalog.datahub_client import DatahubClient

dh = DatahubClient(config=DatahubConfig(
    server="http://datahub-gms:8080",
    token=os.environ["DATAHUB_TOKEN"],
))
# await dh.emit_lineage(upstream_urns=[...], downstream_urn="...")
```

---

## Anti-patterns

**Running dbt models via `DbtArtifactsReader`** — the reader is read-only; it parses compiled artifact JSON. To invoke dbt at runtime, use `subprocess` or the dbt Cloud API.

**Using `AirbyteClient` as a real-time streaming source** — Airbyte syncs are batch operations. For continuous streaming, use native connector sources in `pirn.domains.connectors.streaming`.

---

## Constraints and gotchas

- **Each client requires its own extra:** `pirn[dbt-artifacts]`, `pirn[fivetran]`, `pirn[airbyte]`, `pirn[datahub]`, `pirn[alation]`, `pirn[open-metadata]`.
- **`DbtArtifactsReader` reads files at construction time**, not lazily. Ensure `target/manifest.json` is present before building the tapestry.
- **`DatahubClient` uses the DataHub GMS REST API**, not the Python SDK emitter — no local SDK install required beyond `pirn[datahub]`.
- **`AirbyteClient` uses Airbyte API v1** — requires Airbyte >= 0.50.0.

---

## Quick reference

| Task | How |
|------|-----|
| Read dbt column schema | `DbtArtifactsReader(config=DbtArtifactsConfig(...)).get_model_schema(name)` |
| Trigger Fivetran sync | `FivetranClient(...).trigger_sync(connector_id=...)` |
| Trigger Airbyte sync | `AirbyteClient(...).trigger_sync(connection_id=...)` |
| Publish lineage to DataHub | `DatahubClient(...).emit_lineage(upstream_urns=..., downstream_urn=...)` |
| Search Alation catalog | `AlationClient(...).search(query=...)` |
| Get table metadata from OpenMetadata | `OpenMetadataClient(...).get_table(fqn=...)` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
