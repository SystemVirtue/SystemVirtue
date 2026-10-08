"""MCP Registry client (registry.modelcontextprotocol.io).

Network hard controls from TECHNICAL_COST_CONTROLS.md are enforced here,
before any request leaves the machine:

- explicit provider allowlist (HTTPS + named hosts only);
- fixed timeout and response size cap;
- no credentials, no financial operations of any kind, and no redirects
  to non-allowlisted hosts.

All returned content is untrusted data: it is schema-validated and screened
by the verification pipeline before it can become knowledge (invariant 5).
"""

import json
import urllib.error
import urllib.parse
import urllib.request

ALLOWED_HOSTS = {"registry.modelcontextprotocol.io"}
SCHEME = "https"
FETCH_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
USER_AGENT = "SystemVirtue-MVP/1.0 (+research prototype; no credentials)"

BASE_URL = "https://registry.modelcontextprotocol.io/v0/servers"


class AllowlistError(Exception):
    """A request was refused by the network allowlist."""


class FetchError(Exception):
    """The registry could not be reached or returned unusable data."""


def check_url(url):
    """Enforce the provider allowlist. Raises AllowlistError."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != SCHEME:
        raise AllowlistError("refusing non-HTTPS endpoint: %s" % url)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise AllowlistError("host not in allowlist: %s" % host)
    return url


def build_url(search=None, limit=20, cursor=None):
    params = {"limit": str(int(limit))}
    if search:
        params["search"] = search
    if cursor:
        params["cursor"] = cursor
    return check_url(BASE_URL + "?" + urllib.parse.urlencode(params))


def fetch_servers(search=None, limit=20, cursor=None):
    """Fetch one page of registry server records.

    Returns the parsed JSON document: {"servers": [...], "metadata": {...}}.
    Raises AllowlistError / FetchError; never mutates anything.
    """
    url = build_url(search=search, limit=limit, cursor=cursor)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError("registry unreachable: %s" % exc)
    if len(body) > MAX_RESPONSE_BYTES:
        raise FetchError("response exceeds %d byte cap" % MAX_RESPONSE_BYTES)
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError("registry returned unparseable data: %s" % exc)
    if not isinstance(document, dict) or not isinstance(document.get("servers"), list):
        raise FetchError("registry response missing 'servers' list")
    return document
