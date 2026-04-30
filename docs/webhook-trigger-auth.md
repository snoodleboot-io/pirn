# Webhook Trigger Authentication & Rate Limiting

This guide covers the built-in security controls available on `WebhookTrigger`
and how to layer additional controls at the deployment level.

---

## Quick start — Bearer token auth

Pass the token via an environment variable so it never appears in source code:

```python
import os
from pirn.triggers.http import WebhookTrigger

trigger = WebhookTrigger(path="/run", auth_token=os.environ["PIRN_WEBHOOK_TOKEN"])
```

Callers must supply the header on every request:

```
Authorization: Bearer <token>
```

Requests with a missing or wrong token receive **HTTP 401**:

```json
{"error": "unauthorized"}
```

The comparison uses `hmac.compare_digest` to prevent timing-based token
enumeration.

---

## Rate limiting

Limit inbound requests per IP address to protect downstream resources:

```python
trigger = WebhookTrigger(
    path="/run",
    auth_token=os.environ["PIRN_WEBHOOK_TOKEN"],
    rate_limit_rpm=60,   # max 60 requests per minute per IP
)
```

Requests exceeding the limit receive **HTTP 429**:

```json
{"error": "rate limit exceeded"}
```

The window is a 60-second sliding window; entries older than 60 seconds are
pruned on each check.  There is no persistent state — counts reset if the
process restarts.

---

## Starlette middleware (OAuth2, mTLS, custom auth)

For teams that need more than Bearer tokens, mount custom Starlette middleware
around the trigger's app:

```python
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount

class OAuth2Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization", "")
        if not await _validate_oauth2_token(token):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)

app = Starlette(
    middleware=[Middleware(OAuth2Middleware)],
    routes=[Mount("/", app=trigger.app)],
)
```

The same pattern works for mTLS certificate inspection, HMAC-signed payloads,
or any other request-level check.

---

## Reverse proxy — forwarding the Authorization header (nginx)

When deploying behind nginx, forward the `Authorization` header so middleware
and the trigger's built-in check both receive it:

```nginx
location /run {
    proxy_pass         http://127.0.0.1:8080;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   Authorization     $http_authorization;
}
```

If you terminate auth at the proxy layer and strip the header before passing
upstream, ensure the proxy sets a trusted internal header instead and update
your middleware accordingly.

---

## What NOT to do

- **Do not set `verify=False`** in any HTTP client that calls this endpoint.
  Disabling TLS verification exposes tokens to interception.

- **Do not hardcode tokens in source code.**  Always read secrets from
  environment variables or a secrets manager:

  ```python
  # Bad — never do this
  trigger = WebhookTrigger(path="/run", auth_token="mysecrettoken123")

  # Good
  trigger = WebhookTrigger(path="/run", auth_token=os.environ["PIRN_WEBHOOK_TOKEN"])
  ```

- **Do not log the raw `Authorization` header** or the token value.  Log only
  that authentication succeeded or failed.
