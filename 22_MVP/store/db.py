"""SQLite canonical store for SystemVirtue (CANONICAL_DATA_MODEL.md).

The canonical claim/evidence model is the source of truth; search indexes
are derived (see store.index). Claims are append-only: revisions are new
rows linked with supersedes/superseded_by; historical content is never
overwritten (FR-K03, invariant 9).
"""

import json
import sqlite3
import threading

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id   TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    source_root   TEXT NOT NULL,
    title         TEXT NOT NULL,
    retrieved_at  TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    derived_from  TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,
    aliases         TEXT NOT NULL DEFAULT '[]',
    source_ids      TEXT NOT NULL DEFAULT '{}',
    evidence_ids    TEXT NOT NULL DEFAULT '[]',
    lifecycle_state TEXT NOT NULL DEFAULT 'active',
    valid_from      TEXT,
    valid_until     TEXT,
    history         TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id          TEXT PRIMARY KEY,
    subject           TEXT NOT NULL,
    predicate         TEXT NOT NULL,
    object            TEXT NOT NULL,
    source            TEXT NOT NULL,
    source_type       TEXT NOT NULL,
    evidence_id       TEXT NOT NULL REFERENCES evidence(evidence_id),
    discovered_at     TEXT NOT NULL,
    verified_at       TEXT,
    valid_from        TEXT,
    valid_until       TEXT,
    agent_id          TEXT NOT NULL,
    model_id          TEXT,
    confidence        REAL NOT NULL,
    freshness         TEXT NOT NULL,
    verification_state TEXT NOT NULL,
    contradictions    TEXT NOT NULL DEFAULT '[]',
    policy_state      TEXT NOT NULL,
    history           TEXT NOT NULL DEFAULT '[]',
    supersedes        TEXT,
    superseded_by     TEXT
);

CREATE TABLE IF NOT EXISTS relationships (
    relationship_id    TEXT PRIMARY KEY,
    subject            TEXT NOT NULL,
    predicate          TEXT NOT NULL,
    object             TEXT NOT NULL,
    evidence_id        TEXT NOT NULL REFERENCES evidence(evidence_id),
    confidence         REAL NOT NULL,
    verification_state TEXT NOT NULL,
    valid_from         TEXT,
    valid_until        TEXT,
    history            TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS events (
    event_id         TEXT PRIMARY KEY,
    event_type       TEXT NOT NULL,
    subject          TEXT NOT NULL,
    detected_at      TEXT NOT NULL,
    source           TEXT NOT NULL,
    confidence       REAL NOT NULL,
    affected_entities TEXT NOT NULL DEFAULT '[]',
    required_tasks   TEXT NOT NULL DEFAULT '[]',
    priority         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    action_id           TEXT PRIMARY KEY,
    agent_id            TEXT NOT NULL,
    agent_role          TEXT NOT NULL,
    model               TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    policy_version      TEXT NOT NULL,
    prompt_configuration TEXT NOT NULL,
    tools               TEXT NOT NULL DEFAULT '[]',
    sources             TEXT NOT NULL DEFAULT '[]',
    input_hash          TEXT NOT NULL,
    output_hash         TEXT NOT NULL,
    decision            TEXT NOT NULL,
    verification        TEXT NOT NULL,
    timestamp           TEXT NOT NULL
);
"""


class KnowledgeError(Exception):
    """Raised when an operation would violate an architectural invariant."""


def _dumps(value):
    return json.dumps(value, sort_keys=True)


def _loads(value, default):
    if value is None:
        return default
    return json.loads(value)


class _LockedConn:
    """Serialises a sqlite3 connection across HTTP handler threads."""

    def __init__(self, conn, lock):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_lock", lock)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name in ("_conn", "_lock"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def execute(self, *args, **kwargs):
        with self._lock:
            return self._conn.execute(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        with self._lock:
            return self._conn.executescript(*args, **kwargs)

    def commit(self):
        with self._lock:
            return self._conn.commit()


class Store:
    """Durable knowledge over SQLite. Personal state never lives here
    (invariant 4: user state remains separate from global state)."""

    def __init__(self, path=":memory:"):
        self.path = path
        raw = sqlite3.connect(path, check_same_thread=False)
        self.conn = _LockedConn(raw, threading.RLock())
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)

    def close(self):
        self.conn.close()

    # ------------------------------------------------------------- writes

    def add_evidence(self, ev):
        self.conn.execute(
            "INSERT INTO evidence (evidence_id, source, source_type, source_root, title,"
            " retrieved_at, content_hash, derived_from) VALUES (?,?,?,?,?,?,?,?)",
            (
                ev["evidence_id"], ev["source"], ev["source_type"], ev["source_root"],
                ev["title"], ev["retrieved_at"], ev["content_hash"], ev.get("derived_from"),
            ),
        )
        self.conn.commit()

    def add_entity(self, ent):
        self.conn.execute(
            "INSERT INTO entities (entity_id, entity_type, canonical_name, aliases,"
            " source_ids, evidence_ids, lifecycle_state, valid_from, valid_until, history)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                ent["entity_id"], ent["entity_type"], ent["canonical_name"],
                _dumps(ent.get("aliases", [])), _dumps(ent.get("source_ids", {})),
                _dumps(ent.get("evidence_ids", [])), ent.get("lifecycle_state", "active"),
                ent.get("valid_from"), ent.get("valid_until"), _dumps(ent.get("history", [])),
            ),
        )
        self.conn.commit()

    def add_claim(self, claim):
        """Append a claim. Evidence must exist first (invariant 1:
        evidence precedes durable knowledge)."""
        row = self.conn.execute(
            "SELECT evidence_id FROM evidence WHERE evidence_id = ?",
            (claim["evidence"],),
        ).fetchone()
        if row is None:
            raise KnowledgeError(
                "claim %s references unknown evidence %s: evidence must precede durable knowledge"
                % (claim["claim_id"], claim["evidence"])
            )
        if self.conn.execute(
            "SELECT 1 FROM claims WHERE claim_id = ?", (claim["claim_id"],)
        ).fetchone():
            raise KnowledgeError("claim %s already exists; claims are append-only" % claim["claim_id"])
        self.conn.execute(
            "INSERT INTO claims (claim_id, subject, predicate, object, source, source_type,"
            " evidence_id, discovered_at, verified_at, valid_from, valid_until, agent_id,"
            " model_id, confidence, freshness, verification_state, contradictions, policy_state,"
            " history, supersedes, superseded_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                claim["claim_id"], claim["subject"], claim["predicate"], claim["object"],
                claim["source"], claim["source_type"], claim["evidence"], claim["discovered_at"],
                claim.get("verified_at"), claim.get("valid_from"), claim.get("valid_until"),
                claim["agent_id"], claim.get("model_id"), claim["confidence"], claim["freshness"],
                claim["verification_state"], _dumps(claim.get("contradictions", [])),
                claim["policy_state"], _dumps(claim.get("history", [])),
                claim.get("supersedes"), claim.get("superseded_by"),
            ),
        )
        self.conn.commit()

    def supersede_claim(self, old_id, new_claim):
        """Insert a revision of an existing claim. The old row's content is
        untouched; only the superseded_by pointer and history are appended."""
        old = self.claim(old_id)
        if old is None:
            raise KnowledgeError("cannot supersede unknown claim %s" % old_id)
        if old.get("superseded_by"):
            raise KnowledgeError("claim %s already superseded" % old_id)
        new_claim = dict(new_claim)
        new_claim["supersedes"] = old_id
        self.add_claim(new_claim)
        history = old.get("history", [])
        history.append(
            {
                "at": new_claim["discovered_at"],
                "agent_id": new_claim["agent_id"],
                "action": "superseded",
                "detail": "replaced by %s" % new_claim["claim_id"],
            }
        )
        self.conn.execute(
            "UPDATE claims SET superseded_by = ?, history = ? WHERE claim_id = ?",
            (new_claim["claim_id"], _dumps(history), old_id),
        )
        self.conn.commit()
        return new_claim["claim_id"]

    def update_entity_lifecycle(self, entity_id, state, at, agent_id, detail):
        """Entity-level metadata update: lifecycle state with appended history.
        Claims remain append-only; this never touches claim content."""
        ent = self.entity(entity_id)
        if ent is None:
            raise KnowledgeError("unknown entity %s" % entity_id)
        history = ent.get("history", [])
        history.append({"at": at, "agent_id": agent_id, "action": "lifecycle", "detail": "%s -> %s: %s" % (ent["lifecycle_state"], state, detail)})
        self.conn.execute(
            "UPDATE entities SET lifecycle_state = ?, history = ? WHERE entity_id = ?",
            (state, _dumps(history), entity_id),
        )
        self.conn.commit()

    def add_relationship(self, rel):
        row = self.conn.execute(
            "SELECT evidence_id FROM evidence WHERE evidence_id = ?",
            (rel["evidence_id"],),
        ).fetchone()
        if row is None:
            raise KnowledgeError(
                "relationship %s references unknown evidence %s" % (rel["relationship_id"], rel["evidence_id"])
            )
        self.conn.execute(
            "INSERT INTO relationships (relationship_id, subject, predicate, object, evidence_id,"
            " confidence, verification_state, valid_from, valid_until, history) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                rel["relationship_id"], rel["subject"], rel["predicate"], rel["object"],
                rel["evidence_id"], rel["confidence"], rel["verification_state"],
                rel.get("valid_from"), rel.get("valid_until"), _dumps(rel.get("history", [])),
            ),
        )
        self.conn.commit()

    def add_event(self, event):
        self.conn.execute(
            "INSERT INTO events (event_id, event_type, subject, detected_at, source, confidence,"
            " affected_entities, required_tasks, priority) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event.get("event_id", "evt-untyped"), event["event_type"], event["subject"],
                event["detected_at"], event["source"], event["confidence"],
                _dumps(event.get("affected_entities", [])), _dumps(event.get("required_tasks", [])),
                event["priority"],
            ),
        )
        self.conn.commit()

    def add_audit(self, record):
        self.conn.execute(
            "INSERT INTO audit_log (action_id, agent_id, agent_role, model, model_version,"
            " policy_version, prompt_configuration, tools, sources, input_hash, output_hash,"
            " decision, verification, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record["action_id"], record["agent_id"], record["agent_role"], record["model"],
                record["model_version"], record["policy_version"], record["prompt_configuration"],
                _dumps(record.get("tools", [])), _dumps(record.get("sources", [])),
                record["input_hash"], record["output_hash"], record["decision"],
                record["verification"], record["timestamp"],
            ),
        )
        self.conn.commit()

    # -------------------------------------------------------------- reads

    def _row_to_claim(self, row):
        d = dict(row)
        # present the schema shape: the claim schema names the FK "evidence"
        d["evidence"] = d.pop("evidence_id")
        d["contradictions"] = _loads(d["contradictions"], [])
        d["history"] = _loads(d["history"], [])
        return d

    def claim(self, claim_id):
        row = self.conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        return self._row_to_claim(row) if row else None

    def claims_for(self, subject, include_superseded=False):
        query = "SELECT * FROM claims WHERE subject = ?"
        if not include_superseded:
            query += " AND superseded_by IS NULL"
        query += " ORDER BY predicate, discovered_at"
        return [self._row_to_claim(r) for r in self.conn.execute(query, (subject,))]

    def all_claims(self):
        return [self._row_to_claim(r) for r in self.conn.execute("SELECT * FROM claims")]

    def entity(self, entity_id):
        row = self.conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        return self._row_to_entity(row) if row else None

    def _row_to_entity(self, row):
        d = dict(row)
        d["aliases"] = _loads(d["aliases"], [])
        d["source_ids"] = _loads(d["source_ids"], {})
        d["evidence_ids"] = _loads(d["evidence_ids"], [])
        d["history"] = _loads(d["history"], [])
        return d

    def entities(self, entity_type=None):
        if entity_type:
            rows = self.conn.execute("SELECT * FROM entities WHERE entity_type = ?", (entity_type,))
        else:
            rows = self.conn.execute("SELECT * FROM entities")
        return [self._row_to_entity(r) for r in rows]

    def relationships_for(self, entity_id):
        rows = self.conn.execute(
            "SELECT * FROM relationships WHERE subject = ? OR object = ? ORDER BY predicate",
            (entity_id, entity_id),
        )
        return [dict(r) for r in rows]

    def all_relationships(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM relationships")]

    def relationship(self, relationship_id):
        row = self.conn.execute(
            "SELECT * FROM relationships WHERE relationship_id = ?", (relationship_id,)
        ).fetchone()
        return dict(row) if row else None

    def evidence(self, evidence_id):
        row = self.conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
        return dict(row) if row else None

    def graph(self, center_id, depth=2):
        """Bounded neighbourhood: aggregate rather than dump everything (NFR)."""
        seen_nodes = {center_id}
        edges = []
        frontier = [center_id]
        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for rel in self.relationships_for(node):
                    if rel["relationship_id"] in {e["relationship_id"] for e in edges}:
                        continue
                    edges.append(rel)
                    for other in (rel["subject"], rel["object"]):
                        if other not in seen_nodes:
                            seen_nodes.add(other)
                            next_frontier.append(other)
            frontier = next_frontier
        nodes = [self.entity(eid) for eid in seen_nodes]
        nodes = [n for n in nodes if n]
        return {"center": center_id, "depth": depth, "nodes": nodes, "edges": edges}

    def compare(self, ids):
        result = []
        for eid in ids:
            ent = self.entity(eid)
            if ent is None:
                continue
            result.append(
                {
                    "entity": ent,
                    "claims": self.claims_for(eid),
                    "relationships": self.relationships_for(eid),
                }
            )
        return result

    def audit_records(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM audit_log ORDER BY timestamp, action_id")]

    def ecosystem_events(self):
        out = []
        for row in self.conn.execute("SELECT * FROM events ORDER BY detected_at"):
            d = dict(row)
            d["affected_entities"] = _loads(d["affected_entities"], [])
            d["required_tasks"] = _loads(d["required_tasks"], [])
            out.append(d)
        return out
