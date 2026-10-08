"""SystemVirtue MVP application server (stdlib only).

Serves the accessible exploration UI and the JSON API defined by the
"API Principle" in SYSTEM_REQUIREMENTS.md section 11: entities, claims,
relationships, evidence, search, recommendations, events.

The API deliberately does not expose internal agent authority (section 11),
and personal state (saved entities, history) never reaches this server:
it lives in the browser (invariant 4).
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.ingest import ingest_seed  # noqa: E402
from store.db import Store  # noqa: E402
from store.index import rebuild  # noqa: E402

DB_PATH = os.environ.get("SV_DB", str(_ROOT / "var" / "systemvirtue.db"))
EVENT_LOG = os.environ.get("SV_EVENT_LOG", str(_ROOT / "validation" / "out" / "events.jsonl"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
SEED_PATH = _ROOT / "corpus" / "seed.json"

_event_lock = threading.Lock()


def open_store(db_path=DB_PATH, seed_path=SEED_PATH):
    """Open the canonical store, ingesting the seed corpus on first run."""
    fresh = not Path(db_path).exists()
    store = Store(db_path)
    if fresh:
        ingest_seed(store, str(seed_path))
    return store


def log_ux_event(event, path=None):
    """Append one instrumented UX event (task-tagged) to the JSONL log."""
    path = path or EVENT_LOG
    if not event.get("ts"):
        from datetime import datetime, timezone

        event = dict(event)
        event["ts"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True)
    with _event_lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def read_ux_events(path=None, task=None, condition=None):
    path = path or EVENT_LOG
    if not Path(path).exists():
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if task and ev.get("task") != task:
                continue
            if condition and ev.get("condition") != condition:
                continue
            out.append(ev)
    return out


class KnowledgeAPI:
    """Read-side over the canonical store. Recommendations are derived from
    durable knowledge only (invariant 2)."""

    def __init__(self, store):
        self.store = store
        self.index = rebuild(store)

    # ---------------------------------------------------------- search
    def search(self, params):
        q = params.get("q", [""])[0]
        etype = params.get("type", [""])[0]
        capability = params.get("capability", [""])[0]
        provider = params.get("provider", [""])[0]
        licence = params.get("licence", [""])[0]
        limit = int(params.get("limit", ["25"])[0])

        ids = self.index.search(q) if q else [e["entity_id"] for e in self.store.entities()]
        results = []
        for eid in ids:
            ent = self.store.entity(eid)
            if ent is None:
                continue
            if etype and ent["entity_type"] != etype:
                continue
            if capability and not self._has_relation(eid, "CAPABLE_OF", capability):
                continue
            if provider and not self._linked(eid, provider):
                continue
            if licence and not self._licensed_under(eid, licence):
                continue
            results.append(
                {
                    "entity_id": eid,
                    "entity_type": ent["entity_type"],
                    "canonical_name": ent["canonical_name"],
                    "snippet": self._snippet(eid),
                    "verification_summary": self._verification_summary(eid),
                }
            )
        # total counts every match; results carries the first `limit` of them
        return {"query": q, "results": results[:limit], "total": len(results)}

    def _snippet(self, eid):
        for claim in self.store.claims_for(eid):
            if claim["predicate"] == "DESCRIPTION":
                return claim["object"]
        return ""

    def _verification_summary(self, eid):
        states = {}
        for claim in self.store.claims_for(eid):
            states[claim["verification_state"]] = states.get(claim["verification_state"], 0) + 1
        return states

    def _has_relation(self, subject, predicate, obj):
        for rel in self.store.relationships_for(subject):
            if rel["predicate"] == predicate and rel["subject"] == subject and rel["object"] == obj:
                return True
        return False

    def _linked(self, eid, other):
        for rel in self.store.relationships_for(eid):
            if {rel["subject"], rel["object"]} == {eid, other}:
                return True
        return False

    def _licensed_under(self, eid, licence):
        for claim in self.store.claims_for(eid):
            if claim["predicate"] == "LICENSED_UNDER" and claim["object"] == licence:
                return True
        return False

    # ------------------------------------------------------ entity page
    def entity_detail(self, eid):
        ent = self.store.entity(eid)
        if ent is None:
            return None
        claims = []
        for claim in self.store.claims_for(eid):
            ev = self.store.evidence(claim["evidence"])
            claims.append({"claim": claim, "evidence": ev})
        relationships = []
        for rel in self.store.relationships_for(eid):
            other = rel["object"] if rel["subject"] == eid else rel["subject"]
            other_ent = self.store.entity(other)
            ev = self.store.evidence(rel["evidence_id"])
            relationships.append(
                {
                    "relationship": rel,
                    "direction": "outgoing" if rel["subject"] == eid else "incoming",
                    "other_entity": other_ent,
                    "evidence": ev,
                }
            )
        return {
            "entity": ent,
            "claims": claims,
            "relationships": relationships,
            "freshness": self._freshness(eid),
        }

    def _freshness(self, eid):
        """Freshness transitions are computed at read time: a claim ages even
        though its recorded state stays intact (FR-A05)."""
        from datetime import date

        from pipeline.ingest import assess_freshness

        claims = self.store.claims_for(eid)
        if not claims:
            return {"state": "unknown", "latest_verified_at": None}
        dates = [c["verified_at"] or c["discovered_at"] for c in claims]
        order = ["stale", "aging", "fresh", "unknown"]
        states = set()
        for claim in claims:
            states.add(claim["freshness"])
            states.add(assess_freshness(claim["discovered_at"], date.today().isoformat()))
        state = next((s for s in order if s in states), "unknown")
        return {"state": state, "latest_verified_at": max(dates)}

    # ---------------------------------------------------------- overview
    def overview(self):
        """Aggregated ecosystem picture (NFR: visualisations aggregate
        rather than render every entity). Feeds the multi-resolution UI:
        aggregate -> type -> entity."""
        by_type = {}
        for ent in self.store.entities():
            by_type[ent["entity_type"]] = by_type.get(ent["entity_type"], 0) + 1
        verification = {}
        freshness = {}
        total_claims = 0
        for claim in self.store.all_claims():
            total_claims += 1
            verification[claim["verification_state"]] = verification.get(claim["verification_state"], 0) + 1
            freshness[claim["freshness"]] = freshness.get(claim["freshness"], 0) + 1
        predicates = {}
        for rel in self.store.all_relationships():
            predicates[rel["predicate"]] = predicates.get(rel["predicate"], 0) + 1
        event_types = {}
        for event in self.store.ecosystem_events():
            event_types[event["event_type"]] = event_types.get(event["event_type"], 0) + 1
        return {
            "total_entities": sum(by_type.values()),
            "total_claims": total_claims,
            "total_relationships": sum(predicates.values()),
            "entity_counts_by_type": [
                {"entity_type": t, "count": c}
                for t, c in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "claim_verification": verification,
            "claim_freshness": freshness,
            "relationship_predicates": [
                {"predicate": p, "count": c}
                for p, c in sorted(predicates.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "event_counts_by_type": event_types,
        }

    # ---------------------------------------------------------- explore
    def explore(self, question):
        """Constrained natural-language exploration: every answer is
        retrieval over claims, with citations and stated uncertainty."""
        q = question.strip()
        lowered = q.lower()
        intent, eid = self._resolve_intent(lowered)
        citations = []
        alternatives = []

        if intent == "alternatives" and eid:
            alts = self._related(eid, ("ALTERNATIVE_TO", "SUBSTITUTE_FOR"))
            names = [a["canonical_name"] for a in alts]
            answer = "Alternatives to %s: %s." % (
                self.store.entity(eid)["canonical_name"],
                ", ".join(names) if names else "none recorded in the knowledge base",
            )
            alternatives = [{"entity_id": a["entity_id"], "canonical_name": a["canonical_name"]} for a in alts]
            citations.extend(self._cite_relations(eid, ("ALTERNATIVE_TO", "SUBSTITUTE_FOR")))
        elif intent == "provider" and eid:
            providers = self._related(eid, ("HOSTED_BY", "BELONGS_TO"), direction="incoming") + self._related(
                eid, ("PROVIDES",), direction="incoming"
            )
            answer = "%s is provided by: %s." % (
                self.store.entity(eid)["canonical_name"],
                ", ".join(p["canonical_name"] for p in providers) or "no provider recorded",
            )
            citations.extend(self._cite_claim(eid, "DEVELOPED_BY"))
        elif intent == "capabilities" and eid:
            caps = self._related(eid, ("CAPABLE_OF",))
            tools = self._related(eid, ("EXPOSES",))
            parts = []
            if caps:
                parts.append("provides: " + ", ".join(c["canonical_name"] for c in caps))
            if tools:
                parts.append("exposes tools: " + ", ".join(t["canonical_name"] for t in tools))
            answer = "%s %s." % (
                self.store.entity(eid)["canonical_name"],
                "; ".join(parts) if parts else "has no recorded capabilities",
            )
            citations.extend(self._cite_claim(eid, "DESCRIPTION"))
            citations.extend(self._cite_relations(eid, ("CAPABLE_OF", "EXPOSES")))
        elif intent == "tools_for":
            cap_id = self._match_capability(lowered)
            if cap_id:
                providers = self._related(cap_id, ("CAPABLE_OF",), direction="incoming")
                answer = "Entities providing %s: %s." % (
                    self.store.entity(cap_id)["canonical_name"],
                    ", ".join(p["canonical_name"] for p in providers) or "none recorded",
                )
                citations.extend(self._cite_claim(cap_id, "DESCRIPTION"))
            else:
                answer = "No matching capability found for that question."
        else:
            if eid is None:
                hits = self.index.search(q, limit=1)
                eid = hits[0] if hits else None
            if eid:
                desc = self._cite_claim(eid, "DESCRIPTION")
                answer = desc[0]["object"] if desc else "%s is recorded without a description." % eid
                citations.extend(desc)
            else:
                answer = "No entity in the knowledge base matches that question."

        confidence = max((c["confidence"] for c in citations), default=0.0)
        uncertain = [c for c in citations if c["verification_state"] != "accepted"]
        uncertainty = (
            "Based on %d claim(s); highest confidence %.2f. %d claim(s) are not fully verified."
            % (len(citations), confidence, len(uncertain))
        )
        return {
            "question": q,
            "answer": answer,
            "citations": citations,
            "uncertainty": uncertainty,
            "alternatives": alternatives,
        }

    def _resolve_intent(self, lowered):
        if any(w in lowered for w in ("alternatives", "alternative", "instead of", "compare")):
            return "alternatives", self._match_entity(lowered)
        if any(w in lowered for w in ("who provides", "who develops", "who makes", "who owns", "provider")):
            return "provider", self._match_entity(lowered)
        if any(w in lowered for w in ("what can", "capabilities", "capable")):
            return "capabilities", self._match_entity(lowered)
        if any(w in lowered for w in ("tools for", "how do i", "how can i", "what should i use")):
            return "tools_for", None
        return "describe", self._match_entity(lowered)

    def _match_entity(self, lowered):
        hits = self.index.search(lowered, limit=1)
        return hits[0] if hits else None

    def _match_capability(self, lowered):
        caps = [e for e in self.store.entities("capability")]
        tokens = set(lowered.split())
        best, best_score = None, 0
        for cap in caps:
            score = len(tokens & set((cap["canonical_name"] + " " + cap["entity_id"]).lower().replace("/", " ").replace("-", " ").split()))
            if score > best_score:
                best, best_score = cap["entity_id"], score
        return best

    def _related(self, eid, predicates, direction="outgoing"):
        out = []
        for rel in self.store.relationships_for(eid):
            if rel["predicate"] not in predicates:
                continue
            if direction == "outgoing" and rel["subject"] == eid:
                other = self.store.entity(rel["object"])
            elif direction == "incoming" and rel["object"] == eid:
                other = self.store.entity(rel["subject"])
            else:
                continue
            if other:
                out.append(other)
        return out

    def _cite_claim(self, eid, predicate):
        citations = []
        for claim in self.store.claims_for(eid):
            if claim["predicate"] == predicate:
                citations.append(
                    {
                        "claim_id": claim["claim_id"],
                        "object": claim["object"],
                        "source": claim["source"],
                        "confidence": claim["confidence"],
                        "verification_state": claim["verification_state"],
                    }
                )
        return citations

    def _cite_relations(self, eid, predicates):
        citations = []
        for rel in self.store.relationships_for(eid):
            if rel["predicate"] in predicates:
                ev = self.store.evidence(rel["evidence_id"])
                citations.append(
                    {
                        "claim_id": rel["relationship_id"],
                        "object": "%s %s %s" % (rel["subject"], rel["predicate"], rel["object"]),
                        "source": ev["source"] if ev else "",
                        "confidence": rel["confidence"],
                        "verification_state": rel["verification_state"],
                    }
                )
        return citations

    # ------------------------------------------------------ recommend
    def recommend(self, task=None, capability=None, limit=5):
        """Evidence-backed ranking: reasons, uncertainty and alternatives
        are mandatory outputs (FR-R01/R02/R03). Derived from durable
        knowledge only (invariant 2)."""
        if capability is None and task:
            for rel in self.store.relationships_for(task):
                if rel["predicate"] == "REQUIRES" and rel["subject"] == task:
                    capability = rel["object"]
                    break
        if capability is None:
            return {"task": task, "capability": None, "ranking": [], "uncertainty": "No capability resolved.", "alternatives": []}

        scored = []
        for rel in self.store.relationships_for(capability):
            if rel["predicate"] != "CAPABLE_OF" or rel["object"] != capability:
                continue
            weight = 1.0 if rel["verification_state"] == "accepted" else 0.6
            scored.append((rel["subject"], rel["confidence"] * weight, rel))
        scored.sort(key=lambda t: (-t[1], t[0]))

        ranking = []
        for eid, score, rel in scored[:limit]:
            ent = self.store.entity(eid)
            ranking.append(
                {
                    "entity_id": eid,
                    "canonical_name": ent["canonical_name"] if ent else eid,
                    "score": round(score, 3),
                    "reasons": [
                        "provides capability %s" % capability,
                        "evidence state: %s (confidence %.2f)" % (rel["verification_state"], rel["confidence"]),
                    ],
                }
            )
        alternatives = [
            {"entity_id": r["entity_id"], "canonical_name": r["canonical_name"], "reasons": r["reasons"]}
            for r in ranking[1:3]
        ]
        uncertainty = (
            "Ranked from %d verified capability claim(s) for %s. No live availability, pricing or quota "
            "data is included." % (len(scored), capability)
        )
        return {
            "task": task,
            "capability": capability,
            "ranking": ranking,
            "uncertainty": uncertainty,
            "alternatives": alternatives,
        }


class Handler(BaseHTTPRequestHandler):
    api = None  # injected by create_server

    def log_message(self, fmt, *args):  # keep test output clean
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        params = parse_qs(url.query)

        if path == "/" or path == "/index.html":
            self._send_html((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
        elif path.startswith("/static/"):
            name = unquote(path[len("/static/"):])
            file = (STATIC_DIR / name).resolve()
            if not str(file).startswith(str(STATIC_DIR.resolve())) or not file.is_file():
                self._send_json({"error": "not found"}, 404)
                return
            ctype = {"js": "text/javascript", "css": "text/css", "html": "text/html"}.get(
                file.suffix.lstrip("."), "text/plain"
            )
            body = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/health":
            self._send_json({"status": "ok", "entities": len(self.api.store.entities())})
        elif path == "/api/search":
            self._send_json(self.api.search(params))
        elif path.startswith("/api/entity/"):
            detail = self.api.entity_detail(unquote(path[len("/api/entity/"):]))
            self._send_json(detail if detail else {"error": "not found"}, 200 if detail else 404)
        elif path == "/api/graph":
            center = params.get("center", [""])[0]
            depth = int(params.get("depth", ["2"])[0])
            self._send_json(self.api.store.graph(center, depth))
        elif path == "/api/compare":
            ids = [i for i in params.get("ids", [""])[0].split(",") if i]
            self._send_json({"items": self.api.store.compare(ids)})
        elif path == "/api/explore":
            self._send_json(self.api.explore(params.get("q", [""])[0]))
        elif path == "/api/recommend":
            self._send_json(self.api.recommend(params.get("task", [None])[0], params.get("capability", [None])[0]))
        elif path == "/api/audit":
            self._send_json({"records": self.api.store.audit_records()})
        elif path == "/api/ecosystem-events":
            self._send_json({"events": self.api.store.ecosystem_events()})
        elif path == "/api/overview":
            self._send_json(self.api.overview())
        elif path == "/api/events":
            self._send_json(
                {
                    "events": read_ux_events(
                        task=params.get("task", [None])[0],
                        condition=params.get("condition", [None])[0],
                    )
                }
            )
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        url = urlsplit(self.path)
        if url.path != "/api/events":
            self._send_json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, 400)
            return
        event = {
            "ts": payload.get("ts") or "",
            "participant": payload.get("participant", "anonymous"),
            "condition": "systemvirtue",
            "task": payload.get("task"),
            "action": payload.get("action"),
            "target": payload.get("target"),
            "payload": payload.get("payload", {}),
        }
        log_ux_event(event)
        self._send_json({"logged": True})


def create_server(port=0, db_path=DB_PATH):
    store = open_store(db_path)
    api = KnowledgeAPI(store)

    class BoundHandler(Handler):
        pass

    BoundHandler.api = api
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)
    return server, api


def main():
    port = int(os.environ.get("SV_PORT", "8765"))
    server, _ = create_server(port)
    print("SystemVirtue MVP on http://127.0.0.1:%d" % server.server_address[1])
    server.serve_forever()


if __name__ == "__main__":
    main()
