`pirn.connectors.messaging` provides API clients for human-facing messaging services — it does not implement pub/sub event streaming; use `pirn.connectors.streaming` for Kafka, Kinesis, or RabbitMQ.

---

## Mental model

Each messaging service has a `*Config` (credentials, workspace identifiers) and a `*Client` (live API session). Create the config, pass it to the client constructor, then pass the client to any knot that accepts a `client=` argument. Clients are `PirnOpaqueValue` — create once at startup, reuse across tapestries.

The primary use case is human notification and escalation at the end of a pipeline: a result knot fans output into a messaging sink.

---

## Source map

```
pirn/domains/connectors/messaging/
├── slack_config.py          SlackConfig          — bot_token, channel (default)
├── slack_client.py          SlackClient          — Slack Web API client
├── teams_config.py          TeamsConfig          — webhook_url or tenant + client creds
├── teams_client.py          TeamsClient          — Microsoft Teams webhook/Graph client
├── discord_config.py        DiscordConfig        — bot_token, guild_id
├── discord_client.py        DiscordClient        — Discord REST API client
├── telegram_config.py       TelegramConfig       — bot_token, chat_id (default)
├── telegram_client.py       TelegramClient       — Telegram Bot API client
├── pagerduty_config.py      PagerdutyConfig      — api_key, service_key
└── pagerduty_client.py      PagerdutyClient      — PagerDuty Events API v2 client
```

---

## Canonical pattern

```python
from pirn.connectors.messaging.slack_config import SlackConfig
from pirn.connectors.messaging.slack_client import SlackClient
from pirn import Tapestry, KnotConfig, RunRequest

slack = SlackClient(config=SlackConfig(bot_token=os.environ["SLACK_TOKEN"], channel="#alerts"))

with Tapestry() as t:
    result  = ProcessKnot(_config=KnotConfig(id="process"))
    AlertSink(client=slack, message=result, _config=KnotConfig(id="notify"))

result = await t.run(RunRequest())
```

### PagerDuty — trigger an incident on pipeline failure

```python
from pirn.connectors.messaging.pagerduty_config import PagerdutyConfig
from pirn.connectors.messaging.pagerduty_client import PagerdutyClient

pd = PagerdutyClient(config=PagerdutyConfig(
    api_key=os.environ["PD_API_KEY"],
    service_key=os.environ["PD_SERVICE_KEY"],
))
# pd.trigger(summary, severity, source) — call from on_error callback or a dedicated knot
```

---

## Anti-patterns

**One client per tapestry run** — clients hold HTTP sessions. Create once at startup and reuse. Creating per-run exhausts file descriptors and bypasses connection pooling.

**Using messaging clients for event streaming** — `SlackClient.post_message()` is synchronous and has rate limits. It is not a pub/sub bus. For high-volume event fan-out use `pirn.connectors.streaming`.

---

## Constraints and gotchas

- **Each client requires its own extra:** `pirn[slack]`, `pirn[teams]`, `pirn[discord]`, `pirn[telegram]`, `pirn[pagerduty]`.
- **`TeamsClient` supports two auth modes:** incoming webhook URL (simpler, less permission) and Microsoft Graph API (full features, requires Azure app registration).
- **`PagerdutyClient.trigger()` uses Events API v2** — `service_key` is the integration key, not the service ID.
- **Rate limits are enforced by the upstream service**, not pirn. Add retry logic in the client wrapper for production use.

---

## Quick reference

| Task | How |
|------|-----|
| Post to Slack channel | `SlackClient(config=SlackConfig(bot_token=..., channel=...))` |
| Post to Teams | `TeamsClient(config=TeamsConfig(webhook_url=...))` |
| Send Discord message | `DiscordClient(config=DiscordConfig(bot_token=..., guild_id=...))` |
| Send Telegram message | `TelegramClient(config=TelegramConfig(bot_token=..., chat_id=...))` |
| Trigger PagerDuty incident | `PagerdutyClient(config=PagerdutyConfig(api_key=..., service_key=...))` |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
