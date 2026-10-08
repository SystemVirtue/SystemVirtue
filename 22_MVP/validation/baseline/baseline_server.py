"""Baseline condition for validation: a conventional search + directory UI.

Deliberately minimal: keyword search over names, flat pages with plain
description text. No relationships, no provenance, no verification states,
no comparison, no recommendations — i.e. what a user gets from an ordinary
directory or search engine. This is the comparator UX_VALIDATION.md requires
("improvement over conventional search/directory baselines").
"""

import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.server import open_store, log_ux_event, read_ux_events  # noqa: E402
from store.index import rebuild  # noqa: E402

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{title}</h1>
{body}
</body></html>"""


def esc(text):
    return html.escape(str(text))


class BaselineAPI:
    """The flat directory: names and plain descriptions only."""

    def __init__(self, store):
        self.store = store
        self.index = rebuild(store)

    def directory(self):
        groups = {}
        for ent in self.store.entities():
            groups.setdefault(ent["entity_type"], []).append(ent)
        return groups

    def search(self, q):
        if not q:
            return []
        return [self.store.entity(eid) for eid in self.index.search(q, limit=20) if self.store.entity(eid)]

    def description(self, eid):
        for claim in self.store.claims_for(eid):
            if claim["predicate"] == "DESCRIPTION":
                return claim["object"]
        return "(no description available)"


class Handler(BaseHTTPRequestHandler):
    api = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, html_text, status=200):
        body = html_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        params = parse_qs(url.query)
        api = self.api

        if url.path == "/":
            parts = ["<form action='/search' method='get'>",
                     "<label for='q'>Search</label> <input id='q' name='q'>",
                     "<button type='submit'>Search</button></form>", "<h2>Directory</h2>"]
            for etype in sorted(api.directory()):
                parts.append("<h3>%s</h3><ul>" % esc(etype))
                for ent in api.directory()[etype]:
                    parts.append("<li><a href='/entity/%s'>%s</a></li>" % (esc(ent["entity_id"]), esc(ent["canonical_name"])))
                parts.append("</ul>")
            self._send(PAGE.format(title="AI Capability Directory (baseline)", body="\n".join(parts)))

        elif url.path == "/search":
            q = params.get("q", [""])[0]
            log_ux_event({"ts": None, "participant": params.get("p", ["anonymous"])[0],
                          "condition": "baseline", "task": params.get("task", [None])[0],
                          "action": "search", "target": q, "payload": {"q": q}})
            results = api.search(q)
            parts = ["<p>%d result(s) for %s</p><ul>" % (len(results), esc(q))]
            for ent in results:
                parts.append("<li><a href='/entity/%s'>%s</a></li>" % (esc(ent["entity_id"]), esc(ent["canonical_name"])))
            parts.append("</ul><p><a href='/'>Back to directory</a></p>")
            self._send(PAGE.format(title="Search results", body="\n".join(parts)))

        elif url.path.startswith("/entity/"):
            eid = unquote(url.path[len("/entity/"):])
            ent = api.store.entity(eid)
            if ent is None:
                self._send(PAGE.format(title="Not found", body="<p>No such entry.</p>"), 404)
                return
            log_ux_event({"ts": None, "participant": "anonymous", "condition": "baseline",
                          "task": None, "action": "navigate", "target": eid, "payload": {}})
            body = ["<h2>%s</h2><p>%s</p>" % (esc(ent["canonical_name"]), esc(api.description(eid))),
                    "<p><a href='/'>Back to directory</a></p>"]
            self._send(PAGE.format(title=ent["canonical_name"], body="\n".join(body)))

        else:
            self._send(PAGE.format(title="Not found", body="<p>No such page.</p>"), 404)

    def do_POST(self):
        url = urlsplit(self.path)
        if url.path != "/events":
            self._send(PAGE.format(title="Not found", body="<p>No such page.</p>"), 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        event = {
            "ts": payload.get("ts"),
            "participant": payload.get("participant", "anonymous"),
            "condition": "baseline",
            "task": payload.get("task"),
            "action": payload.get("action"),
            "target": payload.get("target"),
            "payload": payload.get("payload", {}),
        }
        log_ux_event(event)
        body = json.dumps({"logged": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(port=0, db_path=None):
    db_path = db_path or os.environ.get("SV_DB", str(_ROOT / "var" / "systemvirtue.db"))
    store = open_store(db_path)
    api = BaselineAPI(store)

    class BoundHandler(Handler):
        pass

    BoundHandler.api = api
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)
    return server, api


def main():
    server, _ = create_server(int(os.environ.get("SV_BASELINE_PORT", "8766")))
    print("Baseline directory on http://127.0.0.1:%d" % server.server_address[1])
    server.serve_forever()


if __name__ == "__main__":
    main()
