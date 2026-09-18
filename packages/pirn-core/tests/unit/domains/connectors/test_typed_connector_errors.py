"""Every connector refusal raises a typed ``PirnError``, never a bare ``RuntimeError``.

These cases all used to raise ``RuntimeError(...)``, which a caller can only
catch by catching every programming error alongside it. Each assertion here is
on the exact subclass, so it fails against the pre-PIR-873 connectors (a bare
``RuntimeError`` is not a ``ConnectorConfigError``) and passes against these.

The three shapes:

* :class:`ConnectorConfigError` — the connector was never told enough
  (no ``base_url``, no ``api_key``, no query to page).
* :class:`ConnectorClosedError` — no live connection to serve the statement.
* :class:`ConnectorUsageError` — the call is wrong for the object it was made
  on (``close()`` on a transaction handle, a nested transaction).
* :class:`BackendCapabilityError` — the backend is installed but cannot do it.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from pirn.connectors.bi_catalog.alation_client import AlationClient
from pirn.connectors.bi_catalog.alation_config import AlationConfig
from pirn.connectors.bi_catalog.datahub_client import DataHubClient
from pirn.connectors.bi_catalog.datahub_config import DataHubConfig
from pirn.connectors.bi_catalog.dbt_artifacts_config import DbtArtifactsConfig
from pirn.connectors.bi_catalog.dbt_artifacts_reader import DbtArtifactsReader
from pirn.connectors.bi_catalog.fivetran_client import FivetranClient
from pirn.connectors.bi_catalog.fivetran_config import FivetranConfig
from pirn.connectors.bi_catalog.open_metadata_client import OpenMetadataClient
from pirn.connectors.bi_catalog.open_metadata_config import OpenMetadataConfig
from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.cosmosdb_config import CosmosDBConfig
from pirn.connectors.document.cosmosdb_pool import CosmosDBPool
from pirn.connectors.document.couchbase_config import CouchbaseConfig
from pirn.connectors.document.couchbase_pool import CouchbasePool
from pirn.connectors.document.couchdb_config import CouchDBConfig
from pirn.connectors.document.couchdb_pool import CouchDBPool
from pirn.connectors.document.firestore_config import FirestoreConfig
from pirn.connectors.document.firestore_pool import FirestorePool
from pirn.connectors.messaging.discord_client import DiscordClient
from pirn.connectors.messaging.google_chat_client import GoogleChatClient
from pirn.connectors.messaging.pagerduty_client import PagerDutyClient
from pirn.connectors.messaging.pagerduty_config import PagerDutyConfig
from pirn.connectors.messaging.teams_client import TeamsClient
from pirn.connectors.messaging.telegram_client import TelegramClient
from pirn.connectors.observability.grafana_client import GrafanaClient
from pirn.connectors.observability.grafana_config import GrafanaConfig
from pirn.connectors.observability.prometheus_client import PrometheusClient
from pirn.connectors.observability.prometheus_config import PrometheusConfig
from pirn.connectors.saas.airtable_client import AirtableClient
from pirn.connectors.saas.amplitude_client import AmplitudeClient
from pirn.connectors.saas.amplitude_config import AmplitudeConfig
from pirn.connectors.saas.google_analytics_client import GoogleAnalyticsClient
from pirn.connectors.saas.jira_client import JiraClient
from pirn.connectors.saas.mixpanel_client import MixpanelClient
from pirn.connectors.saas.mixpanel_config import MixpanelConfig
from pirn.connectors.saas.salesforce_client import SalesforceClient
from pirn.connectors.saas.zendesk_client import ZendeskClient
from pirn.connectors.timeseries.kdb_config import KdbConfig
from pirn.connectors.timeseries.kdb_pool import KdbPool
from pirn.connectors.timeseries.victoriametrics_config import VictoriaMetricsConfig
from pirn.connectors.timeseries.victoriametrics_pool import VictoriaMetricsPool
from pirn.exceptions.backend_capability_error import BackendCapabilityError
from pirn.exceptions.connector_closed_error import ConnectorClosedError
from pirn.exceptions.connector_config_error import ConnectorConfigError
from pirn.exceptions.pirn_error import PirnError

Call = Callable[[], Coroutine[Any, Any, object]]


class _FakeHttp:
    """The slice of an httpx client these connectors touch, with no network."""

    async def post(self, url: str, *, json: Any = None, headers: Any = None) -> Any:
        raise AssertionError(f"POST {url} should never have been attempted")

    async def request(self, method: str, url: str, **_: Any) -> Any:
        raise AssertionError(f"{method} {url} should never have been attempted")

    async def aclose(self) -> None:
        return None


def _gc() -> Call:
    client = GoogleChatClient(config=None, client=_FakeHttp())
    return lambda: client.send_message("hi")


def _teams() -> Call:
    client = TeamsClient(config=None, client=_FakeHttp())
    return lambda: client.send_message("hi")


def _discord() -> Call:
    client = DiscordClient(config=None, client=_FakeHttp())
    return lambda: client.send_message("hi")


def _telegram() -> Call:
    client = TelegramClient(config=None, client=_FakeHttp())
    return lambda: client.send_message("1", "hi")


def _pagerduty_routing() -> Call:
    client = PagerDutyClient(PagerDutyConfig(api_key="k"), client=_FakeHttp())
    return lambda: client.trigger_incident(summary="s", source="src", severity="error")


def _pagerduty_api_key() -> Call:
    client = PagerDutyClient(config=None, client=_FakeHttp())
    return lambda: client.list_incidents()


def _airtable() -> Call:
    client = AirtableClient(config=None, client=_FakeHttp())
    return lambda: client.list_records()


def _salesforce() -> Call:
    client = SalesforceClient(config=None, client=object())
    return lambda: client.fetch_page()


def _jira() -> Call:
    client = JiraClient(config=None, client=object())
    return lambda: client.fetch_page()


def _analytics() -> Call:
    client = GoogleAnalyticsClient(config=None, client=object())
    return lambda: client.fetch_page()


def _dbt() -> Call:
    reader = DbtArtifactsReader(DbtArtifactsConfig())
    return lambda: reader.load_manifest()


def _grafana_datasource() -> Call:
    client = GrafanaClient(GrafanaConfig(base_url="https://g.example"), client=object())
    return lambda: client.query("up")


def _grafana_base_url() -> Call:
    client = GrafanaClient(GrafanaConfig())
    return lambda: client.request("GET", "/api/health")


def _prometheus() -> Call:
    client = PrometheusClient(PrometheusConfig())
    return lambda: client.request("GET", "/api/v1/query")


def _datahub() -> Call:
    client = DataHubClient(DataHubConfig())
    return lambda: client.request("GET", "/entities")


def _alation() -> Call:
    client = AlationClient(AlationConfig())
    return lambda: client.request("GET", "/integration/v2/datasource/")


def _alation_token() -> Call:
    client = AlationClient(AlationConfig(base_url="https://a.example"))
    return lambda: client.request("GET", "/integration/v2/datasource/")


def _open_metadata() -> Call:
    client = OpenMetadataClient(OpenMetadataConfig())
    return lambda: client.request("GET", "/api/v1/tables")


def _open_metadata_token() -> Call:
    client = OpenMetadataClient(OpenMetadataConfig(host_url="https://om.example"))
    return lambda: client.request("GET", "/api/v1/tables")


def _fivetran() -> Call:
    client = FivetranClient(FivetranConfig())
    return lambda: client.request("GET", "/groups")


def _mixpanel() -> Call:
    client = MixpanelClient(MixpanelConfig())
    return lambda: client.request("POST", "/track", body={"event": "signup"})


def _amplitude() -> Call:
    client = AmplitudeClient(AmplitudeConfig())
    return lambda: client.request("POST", "/track", body={"event": "signup"})


CONFIG_CASES: dict[str, Callable[[], Call]] = {
    "google_chat.webhook_url": _gc,
    "teams.webhook_url": _teams,
    "discord.webhook_url": _discord,
    "telegram.bot_token": _telegram,
    "pagerduty.routing_key": _pagerduty_routing,
    "pagerduty.api_key": _pagerduty_api_key,
    "airtable.api_key": _airtable,
    "salesforce.soql_query": _salesforce,
    "jira.jql": _jira,
    "google_analytics.report_request": _analytics,
    "dbt_artifacts.target_path": _dbt,
    "grafana.datasource_uid": _grafana_datasource,
    "grafana.base_url": _grafana_base_url,
    "prometheus.base_url": _prometheus,
    "datahub.gms_url": _datahub,
    "alation.base_url": _alation,
    "alation.refresh_token": _alation_token,
    "open_metadata.host_url": _open_metadata,
    "open_metadata.jwt_token": _open_metadata_token,
    "fivetran.api_key": _fivetran,
    "mixpanel.project_token": _mixpanel,
    "amplitude.api_key": _amplitude,
}


class TestMissingConfigurationIsTyped:
    @pytest.mark.parametrize("name", sorted(CONFIG_CASES))
    async def test_raises_connector_config_error(self, name: str) -> None:
        call = CONFIG_CASES[name]()
        with pytest.raises(ConnectorConfigError):
            await call()

    async def test_the_typed_error_is_still_a_pirn_error(self) -> None:
        call = CONFIG_CASES["prometheus.base_url"]()
        with pytest.raises(PirnError):
            await call()


class _UnconnectedFirestorePool(FirestorePool):
    async def _ensure_client(self) -> None:
        return None


class _UnconnectedCosmosPool(CosmosDBPool):
    async def _ensure_container(self) -> None:
        return None


class _UnconnectedCouchDBPool(CouchDBPool):
    async def _ensure_session(self) -> None:
        return None


class _UnconnectedCouchbasePool(CouchbasePool):
    async def _ensure_cluster(self) -> None:
        return None


class _UnconnectedKdbPool(KdbPool):
    async def _ensure_connection(self) -> None:
        return None


class _UnconnectedVictoriaMetricsPool(VictoriaMetricsPool):
    async def _ensure_client(self) -> None:
        return None


NOT_CONNECTED_POOLS: dict[str, Callable[[], DatabaseConnectionPool]] = {
    "firestore": lambda: _UnconnectedFirestorePool(FirestoreConfig(project_id="p", collection="c")),
    "cosmosdb": lambda: _UnconnectedCosmosPool(
        CosmosDBConfig(endpoint="https://c.example", key="k", database="d", container="c")
    ),
    "couchdb": lambda: _UnconnectedCouchDBPool(CouchDBConfig(database="d")),
    "couchbase": lambda: _UnconnectedCouchbasePool(
        CouchbaseConfig(username="u", password="p", bucket="b")
    ),
    "kdb": lambda: _UnconnectedKdbPool(KdbConfig()),
    "victoriametrics": lambda: _UnconnectedVictoriaMetricsPool(VictoriaMetricsConfig()),
}


class TestNoLiveConnectionIsTyped:
    """A driver that hands back nothing reports the same type a closed pool does.

    Each subclass above stands in for exactly that: ``_ensure_*`` returns
    without producing a connection, which is what a driver handshake yielding
    ``None`` looks like from the statement method's side.
    """

    @pytest.mark.parametrize("name", sorted(NOT_CONNECTED_POOLS))
    async def test_execute_raises_connector_closed_error(self, name: str) -> None:
        pool = NOT_CONNECTED_POOLS[name]()
        with pytest.raises(ConnectorClosedError, match="not connected"):
            await pool.execute("SELECT 1")


class TestBackendCapabilityIsTyped:
    async def test_zendesk_client_without_a_request_entry_point(self) -> None:
        client = ZendeskClient(config=None, client=object())
        with pytest.raises(BackendCapabilityError, match="request entry-point"):
            await client.request("GET", "/api/v2/tickets.json")
