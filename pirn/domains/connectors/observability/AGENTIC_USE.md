`pirn.domains.connectors.observability` provides clients for Datadog, Grafana, Prometheus, and OpenTelemetry — it does not replace `pirn.emitters`; these clients are for pushing metrics and events from within pipeline knots, not for tapestry-level lifecycle observability.

---

## Mental model

Each observability backend has a `*Config` (API endpoint, credentials) and a `*Client` or emitter. Use these when a knot needs to report a metric, annotation, or span to an external observability system as part of its business logic. For tapestry-level lifecycle events (run started, knot completed, run failed), use `pirn.emitters` instead.

`OpentelemetryEmitter` is dual-purpose: it implements the `pirn.emitters` interface **and** can be used standalone for direct span/metric emission.

---

## Source map

```
pirn/domains/connectors/observability/
├── datadog_config.py         DatadogConfig         — api_key, site (e.g. datadoghq.com), tags
├── datadog_client.py         DatadogClient         — Datadog Metrics/Events/Logs API
├── grafana_config.py         GrafanaConfig         — base_url, api_key, org_id
├── grafana_client.py         GrafanaClient         — Grafana HTTP API (annotations, alerts, datasources)
├── prometheus_config.py      PrometheusConfig      — pushgateway_url, job, grouping_key
├── prometheus_client.py      PrometheusClient      — Prometheus Pushgateway client (push metrics)
├── opentelemetry_config.py   OpentelemetryConfig   — endpoint, protocol (grpc/http), headers, resource_attrs
└── opentelemetry_emitter.py  OpentelemetryEmitter  — pirn emitter + standalone OTel span/metric emitter
```

---

## Canonical pattern

### Push a metric to Datadog after processing

```python
from pirn.domains.connectors.observability.datadog_config import DatadogConfig
from pirn.domains.connectors.observability.datadog_client import DatadogClient
from pirn import Tapestry, KnotConfig, RunRequest

dd = DatadogClient(config=DatadogConfig(
    api_key=os.environ["DD_API_KEY"], site="datadoghq.com"
))

with Tapestry() as t:
    result = ProcessKnot(_config=KnotConfig(id="process"))
    MetricEmitKnot(client=dd, metric="pipeline.records_processed",
                   value=result, _config=KnotConfig(id="metrics"))
```

### OpenTelemetry as a tapestry emitter

```python
from pirn.domains.connectors.observability.opentelemetry_config import OpentelemetryConfig
from pirn.domains.connectors.observability.opentelemetry_emitter import OpentelemetryEmitter

otel = OpentelemetryEmitter(config=OpentelemetryConfig(
    endpoint="http://otel-collector:4317",
    protocol="grpc",
))

with Tapestry(emitters=[otel]) as t:
    ...
```

### Push metrics to Prometheus Pushgateway

```python
from pirn.domains.connectors.observability.prometheus_config import PrometheusConfig
from pirn.domains.connectors.observability.prometheus_client import PrometheusClient

prom = PrometheusClient(config=PrometheusConfig(
    pushgateway_url="http://pushgateway:9091",
    job="pirn-pipeline",
))
# prom.push({"pipeline_duration_seconds": elapsed})
```

---

## Anti-patterns

**Replacing `pirn.emitters` with these clients** — `pirn.emitters` hook into the tapestry engine lifecycle (knot start/end, run result). These clients are for business-logic metrics. Use both together for full coverage.

**Using `GrafanaClient` to push metrics** — Grafana reads metrics from data sources; it does not ingest them. Push metrics to Prometheus or InfluxDB, then visualise in Grafana.

---

## Constraints and gotchas

- **Each client requires its own extra:** `pirn[datadog]`, `pirn[grafana]`, `pirn[prometheus]`, `pirn[opentelemetry]`.
- **`PrometheusClient` uses the Pushgateway**, which is suitable for batch/short-lived jobs. Do not use it for long-running services where a pull-based exporter is more appropriate.
- **`OpentelemetryEmitter` spans follow the tapestry run hierarchy** — each knot's `process()` is wrapped in a child span under the root run span.
- **`DatadogClient` uses the v2 API.** Metrics must use the Distribution or Gauge type; the v1 legacy `series` endpoint is not used.

---

## Quick reference

| Task | How |
|------|-----|
| Push metric to Datadog | `DatadogClient(config=DatadogConfig(...)).send_metric(name, value, tags)` |
| Create Grafana annotation | `GrafanaClient(config=GrafanaConfig(...)).create_annotation(text, tags)` |
| Push metrics to Prometheus | `PrometheusClient(config=PrometheusConfig(...)).push({metric: value})` |
| Emit OTel spans for tapestry runs | `Tapestry(emitters=[OpentelemetryEmitter(...)])` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
