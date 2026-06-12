`pirn.connectors.saas` provides API clients for SaaS platforms — it does not process or transform the data returned; wire clients into knots that call their methods and emit structured records downstream.

---

## Mental model

Each SaaS service has a `*Config` (API credentials, workspace/org identifiers) and a `*Client` (thin async wrapper around the vendor REST API). Clients are `PirnOpaqueValue` — create once at startup, pass as config constants to knots. All clients expose an async `request()` method; higher-level helpers (list, get, create) are defined per client.

---

## Source map

```
pirn/domains/connectors/saas/
├── stripe_config.py           StripeConfig           — api_key, webhook_secret
├── stripe_client.py           StripeClient           — Stripe API (payments, subscriptions, events)
├── salesforce_config.py       SalesforceConfig       — instance_url, client_id, client_secret, username
├── salesforce_client.py       SalesforceClient       — Salesforce REST API (SOQL, objects, bulk)
├── hubspot_config.py          HubspotConfig          — access_token
├── hubspot_client.py          HubspotClient          — HubSpot CRM API (contacts, deals, pipelines)
├── jira_config.py             JiraConfig             — base_url, user, api_token
├── jira_client.py             JiraClient             — Jira REST API v3 (issues, projects, boards)
├── github_config.py           GithubConfig           — token, base_url (for GHE)
├── github_client.py           GithubClient           — GitHub REST + GraphQL API
├── zendesk_config.py          ZendeskConfig          — subdomain, user, api_token
├── zendesk_client.py          ZendeskClient          — Zendesk Support API (tickets, users, macros)
├── shopify_config.py          ShopifyConfig          — shop_domain, access_token
├── shopify_client.py          ShopifyClient          — Shopify Admin REST + GraphQL API
├── twilio_config.py           TwilioConfig           — account_sid, auth_token
├── twilio_client.py           TwilioClient           — Twilio (SMS, voice, verify)
├── airtable_config.py         AirtableConfig         — api_key, base_id
├── airtable_client.py         AirtableClient         — Airtable REST API (records, tables)
├── amplitude_config.py        AmplitudeConfig        — api_key, secret_key
├── amplitude_client.py        AmplitudeClient        — Amplitude Analytics API (events, cohorts)
├── mixpanel_config.py         MixpanelConfig         — project_token, api_secret
├── mixpanel_client.py         MixpanelClient         — Mixpanel Ingestion + Data Export API
├── google_analytics_config.py GoogleAnalyticsConfig  — property_id, credentials_json
└── google_analytics_client.py GoogleAnalyticsClient  — GA4 Data API (reports, metadata)
```

---

## Canonical pattern

```python
from pirn.connectors.saas.stripe_config import StripeConfig
from pirn.connectors.saas.stripe_client import StripeClient
from pirn import Tapestry, KnotConfig, RunRequest

stripe = StripeClient(config=StripeConfig(api_key=os.environ["STRIPE_KEY"]))

with Tapestry() as t:
    charges = StripeListChargesKnot(client=stripe, limit=100, _config=KnotConfig(id="charges"))
    ProcessKnot(data=charges, _config=KnotConfig(id="process"))

result = await t.run(RunRequest())
```

### Salesforce SOQL query

```python
from pirn.connectors.saas.salesforce_config import SalesforceConfig
from pirn.connectors.saas.salesforce_client import SalesforceClient

sf = SalesforceClient(config=SalesforceConfig(
    instance_url="https://myorg.my.salesforce.com",
    client_id=os.environ["SF_CLIENT_ID"],
    client_secret=os.environ["SF_CLIENT_SECRET"],
    username=os.environ["SF_USERNAME"],
))
# sf.query("SELECT Id, Name FROM Account WHERE CreatedDate = TODAY")
```

---

## Anti-patterns

**Creating a client inside the tapestry block** — clients hold OAuth tokens and connection sessions. Creating per-run triggers unnecessary re-authentication and may exhaust API rate limits.

**Using SaaS clients for high-volume streaming** — SaaS REST APIs have rate limits (e.g. Stripe: 100 req/s, GitHub: 5000 req/hr). For high-volume fan-out, batch requests using the client's bulk/batch endpoints where available.

---

## Constraints and gotchas

- **Each client requires its own extra:** `pirn[stripe]`, `pirn[salesforce]`, `pirn[hubspot]`, `pirn[jira]`, `pirn[github]`, etc.
- **`SalesforceClient` uses OAuth2 client-credentials flow.** The `username` is only needed for user-context operations.
- **`GithubClient` supports both REST and GraphQL.** Use `.graphql(query)` for paginated or nested resource fetches.
- **`TwilioClient` sends real SMS/calls in production.** Always use test credentials (`AC` prefix test SID) in non-production environments.
- **`GoogleAnalyticsClient` requires the GA4 Data API**, not the Universal Analytics API. Properties must be migrated to GA4.

---

## Quick reference

| Platform | Config | Client |
|----------|--------|--------|
| Stripe | `StripeConfig` | `StripeClient` |
| Salesforce | `SalesforceConfig` | `SalesforceClient` |
| HubSpot | `HubspotConfig` | `HubspotClient` |
| Jira | `JiraConfig` | `JiraClient` |
| GitHub | `GithubConfig` | `GithubClient` |
| Zendesk | `ZendeskConfig` | `ZendeskClient` |
| Shopify | `ShopifyConfig` | `ShopifyClient` |
| Twilio | `TwilioConfig` | `TwilioClient` |
| Airtable | `AirtableConfig` | `AirtableClient` |
| Amplitude | `AmplitudeConfig` | `AmplitudeClient` |
| Mixpanel | `MixpanelConfig` | `MixpanelClient` |
| Google Analytics | `GoogleAnalyticsConfig` | `GoogleAnalyticsClient` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
