"""``PrivateHttpRequestTool`` — the one HTTP fetch tool allowed inside the perimeter.

The private/loopback sibling of
:class:`~pirn_agents.tools.web.http_request_tool.HttpRequestTool`.  Everything
else is identical — GET/HEAD only, the pinned vetted endpoint, the streamed and
truncated body — but the SSRF guard's private-address check is off, so this tool
can reach ``localhost``, RFC1918 addresses and link-local metadata endpoints.

Reaching inside the perimeter is chosen by *offering this class* rather than by
a knot input or a call argument, so no upstream knot's output and nothing the
model sends can turn a public-only fetch tool into an internal one (PIR-817).  A
deployment wanting an internal reach *and* an allowlist declares a subclass of
this class setting ``_allowed_hosts``.

References:
    [1] OWASP — Server Side Request Forgery Prevention Cheat Sheet:
        https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
"""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.tools.web.http_request_tool import HttpRequestTool


class PrivateHttpRequestTool(HttpRequestTool):
    """Fetch an http(s) URL (GET/HEAD) that may resolve to a private address."""

    tool_name: ClassVar[str] = "private_http_request"

    _allow_private: ClassVar[bool] = True
