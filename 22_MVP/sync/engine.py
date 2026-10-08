"""Scheduled MCP Registry sync (FR-A01 discovery, FR-A05 freshness).

Feeds registry updates through the existing verification pipeline instead of
manual re-curation:

    fetch (allowlisted) -> normalise -> plan (read-only diff) -> apply
        apply = pipeline commit for new knowledge
                policy-checked supersede for changed claims (history kept)
                ChangeEvents for every detected change (SYSTEM_REQUIREMENTS §7)
                audit rows for every action (invariant 9)

Failure semantics (NFR availability): if the registry is unreachable or
returns unusable data, nothing in the knowledge base is touched.

Scheduling: run periodically via cron/launchd (see validation/RUNBOOK.md) or
`engine.py --daemon --interval 86400`.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.ingest import (  # noqa: E402
    EVENT_SCHEMA,
    Pipeline,
    classify_risk,
    normalise,
    policy_decision,
    VERIFICATION_BY_POLICY,
)
from schemas.validate import validate  # noqa: E402

SYNC_AGENT = "sync-agent-v1"
SYNC_CONTRACT_ROLE = "research"
REGISTRY_ROOT = "registry.modelcontextprotocol.io"
REQUIRED_TASKS = ["task-sync-verify"]

MUTABLE_PREDICATES = ("DESCRIPTION", "REGISTRY_VERSION", "REGISTRY_STATUS")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name):
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "unnamed"


def _hash8(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def normalize_record(item):
    """One registry item -> canonical observation dict (untrusted input)."""
    server = item.get("server") or {}
    meta = (item.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {}
    name = server.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("registry record has no server.name")
    slug = slugify(name)
    description = (server.get("description") or "").strip()
    version = str(server.get("version") or "").strip()
    status = str(meta.get("status") or "unknown").strip()
    packages = server.get("packages") or []
    remotes = server.get("remotes") or []
    package_summary = ", ".join(
        "%s:%s@%s" % (p.get("registryType", "?"), p.get("identifier", "?"), p.get("version", "?"))
        for p in packages[:5]
    )
    remote_summary = ", ".join(r.get("url", "?") for r in remotes[:5])
    raw = json.dumps(server, sort_keys=True)
    content_hash = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return {
        "name": name,
        "slug": slug,
        "entity_id": "mcp-server/" + slug,
        "description": description,
        "version": version,
        "status": status,
        "is_latest": bool(meta.get("isLatest", True)),
        "updated_at": meta.get("updatedAt") or meta.get("publishedAt") or "",
        "published_at": meta.get("publishedAt") or "",
        "package_summary": package_summary,
        "remote_summary": remote_summary,
        "content_hash": content_hash,
        "hash8": content_hash[7:15],
    }


def dedupe_latest(observations):
    """Registry lists every version; keep one observation per server name,
    preferring the record marked isLatest (else the most recently updated)."""
    by_name = {}
    for obs in observations:
        current = by_name.get(obs["name"])
        if current is None:
            by_name[obs["name"]] = obs
            continue
        if obs["is_latest"] and not current["is_latest"]:
            by_name[obs["name"]] = obs
        elif obs["is_latest"] == current["is_latest"] and obs["updated_at"] > current["updated_at"]:
            by_name[obs["name"]] = obs
    return list(by_name.values())


class RegistrySync:
    def __init__(self, store, now="2026-10-09", dry_run=False, agent_id=SYNC_AGENT):
        self.store = store
        self.now = now
        self.dry_run = dry_run
        self.pipeline = Pipeline(store, agent_id=agent_id, now=now)

    # ------------------------------------------------------------ artifacts
    def evidence_record(self, obs):
        return {
            "evidence_id": "ev-registry-%s-%s" % (obs["slug"], obs["hash8"]),
            "source": "https://%s/v0/servers?search=%s" % (REGISTRY_ROOT, obs["name"]),
            "source_type": "registry",
            "source_root": REGISTRY_ROOT,
            "title": "MCP Registry record: %s" % obs["name"],
            "retrieved_at": self.now,
            "content_hash": obs["content_hash"],
            "derived_from": None,
            "excerpt": (obs["description"] or "registry record %s version %s" % (obs["name"], obs["version"]))[:400],
        }

    def entity_record(self, obs):
        return {
            "entity_id": obs["entity_id"],
            "entity_type": "mcp_server",
            "canonical_name": obs["name"],
            "aliases": [obs["name"]],
            "source_ids": {"registry": obs["name"]},
            "evidence_ids": ["ev-registry-%s-%s" % (obs["slug"], obs["hash8"])],
            "lifecycle_state": "active",
            "valid_from": self.now,
            "valid_until": None,
            "history": [],
        }

    def claim_record(self, obs, predicate, obj, confidence, claim_id=None):
        claim_id = claim_id or "claim-registry-%s-%s" % (predicate.lower().replace("_", "-"), obs["slug"])
        return {
            "claim_id": claim_id,
            "subject": obs["entity_id"],
            "predicate": predicate,
            "object": obj,
            "source": "https://%s/v0/servers?search=%s" % (REGISTRY_ROOT, obs["name"]),
            "source_type": "registry",
            "evidence": "ev-registry-%s-%s" % (obs["slug"], obs["hash8"]),
            "discovered_at": self.now,
            "verified_at": self.now,
            "valid_from": self.now,
            "valid_until": None,
            "agent_id": self.pipeline.agent_id,
            "model_id": "registry-sync",
            "confidence": confidence,
            "freshness": "fresh",
            "verification_state": "conditional",
            "contradictions": [],
            "policy_state": "conditional-accepted",
            "history": [],
            "supersedes": None,
            "superseded_by": None,
        }

    def change_event(self, obs, event_type, priority, detail, field=None):
        suffix = "-" + field if field else ""
        return {
            "event_id": "evt-registry-%s-%s%s-%s" % (obs["slug"], event_type.split("_")[0], suffix, obs["hash8"]),
            "event_type": event_type,
            "subject": obs["entity_id"],
            "detected_at": self.now,
            "source": "https://%s/v0/servers?search=%s" % (REGISTRY_ROOT, obs["name"]),
            "confidence": 0.9,
            "affected_entities": [obs["entity_id"]],
            "required_tasks": list(REQUIRED_TASKS),
            "priority": priority,
        }

    # -------------------------------------------------------------- plan
    def plan(self, obs):
        """Read-only diff of one observation against the store."""
        entity = self.store.entity(obs["entity_id"])
        if entity is None:
            return {"action": "create", "obs": obs, "changed": {}}
        current = {}
        for claim in self.store.claims_for(obs["entity_id"]):
            if claim["predicate"] in MUTABLE_PREDICATES:
                current[claim["predicate"]] = claim
        changed = {}
        desired = {
            "DESCRIPTION": obs["description"],
            "REGISTRY_VERSION": obs["version"],
            "REGISTRY_STATUS": obs["status"],
        }
        for predicate, new_value in desired.items():
            if not new_value:
                continue
            old = current.get(predicate)
            if old is None:
                changed[predicate] = (None, new_value)
            elif old["object"] != new_value:
                changed[predicate] = (old, new_value)
        return {"action": "revise" if changed else "none", "obs": obs, "changed": changed}

    # -------------------------------------------------------------- apply
    def apply(self, plan):
        obs = plan["obs"]
        if plan["action"] == "create":
            return self._apply_create(obs)
        if plan["action"] == "revise":
            return self._apply_revise(obs, plan["changed"])
        return {"change": "none", "entity_id": obs["entity_id"]}

    def _apply_create(self, obs):
        ev = self.evidence_record(obs)
        claims = [self.claim_record(obs, "REGISTRY_NAME", obs["name"], 0.95)]
        if obs["description"]:
            claims.append(self.claim_record(obs, "DESCRIPTION", obs["description"], 0.85))
        if obs["version"]:
            claims.append(self.claim_record(obs, "REGISTRY_VERSION", obs["version"], 0.9))
        claims.append(self.claim_record(obs, "REGISTRY_STATUS", obs["status"], 0.9))
        relationship = {
            "relationship_id": "rel-%s-available-through-mcp-registry" % obs["slug"],
            "subject": obs["entity_id"],
            "predicate": "AVAILABLE_THROUGH",
            "object": "source/mcp-registry",
            "evidence_id": ev["evidence_id"],
            "confidence": 0.9,
            "verification_state": "conditional",
            "valid_from": self.now,
            "valid_until": None,
            "history": [],
        }
        fragment = {
            "evidence": [ev],
            "entities": [self.entity_record(obs)],
            "claims": claims,
            "relationships": [relationship],
            "events": [self.change_event(obs, "capability_change", "medium", "new registry entry")],
        }
        if self.dry_run:
            return {"change": "create", "entity_id": obs["entity_id"], "dry_run": True,
                    "claims": [c["claim_id"] for c in claims]}
        report = self.pipeline.run(fragment)
        return {"change": "create", "entity_id": obs["entity_id"],
                "decisions": report["decisions"], "counts": report["counts"]}

    def _apply_revise(self, obs, changed):
        results = {"change": "revise", "entity_id": obs["entity_id"], "fields": {}}
        ev = self.evidence_record(obs)
        evidence_added = False
        for predicate, (old_claim, new_value) in changed.items():
            field = predicate.lower().replace("_", "-")
            claim_id = "claim-registry-%s-%s-%s" % (field, obs["slug"], obs["hash8"])
            revision = self.claim_record(obs, predicate, new_value, 0.9, claim_id=claim_id)
            if old_claim is not None:
                revision["supersedes"] = old_claim["claim_id"]

            ctx = {
                "structural_errors": normalise(revision),
                "freshness": "fresh",
                "authoritative": True,
                "confidence": revision["confidence"],
                "corroborators": 0,
                "contradictions": [],
                "risk": classify_risk(predicate),
            }
            decision, rationale = policy_decision(ctx)
            revision["freshness"] = "fresh"
            revision["policy_state"] = decision
            revision["verification_state"] = VERIFICATION_BY_POLICY[decision]
            revision["history"] = [{"at": self.now, "agent_id": self.pipeline.agent_id,
                                    "action": "policy-decision", "detail": rationale}]

            if self.dry_run:
                results["fields"][predicate] = {"decision": decision, "dry_run": True,
                                                "old": old_claim["object"] if old_claim else None,
                                                "new": new_value}
                continue

            if decision == "rejected":
                self.pipeline.record_audit(decision, revision["verification_state"],
                                           [revision["source"]],
                                           {"revision": {"claim_id": claim_id}},
                                           {"revision": {"decision": decision}})
                results["fields"][predicate] = {"decision": decision, "rationale": rationale}
                continue

            if self.store.evidence(ev["evidence_id"]) is None:
                self.store.add_evidence(ev)
                evidence_added = True
            if old_claim is None:
                self.store.add_claim(revision)
            else:
                self.store.supersede_claim(old_claim["claim_id"], revision)

            field = predicate.lower().replace("_", "-")
            if predicate == "DESCRIPTION":
                event = self.change_event(obs, "capability_change", "low", "description updated", field=field)
            elif predicate == "REGISTRY_VERSION":
                event = self.change_event(obs, "capability_change", "low", "version updated", field=field)
            elif new_value.lower() in ("deprecated", "inactive", "removed"):
                event = self.change_event(obs, "deprecation", "high", "status: %s" % new_value, field=field)
            else:
                event = self.change_event(obs, "capability_change", "low", "status: %s" % new_value, field=field)
            errors = validate(event, EVENT_SCHEMA)
            if not errors:
                self.store.add_event(event)

            self.pipeline.record_audit(decision, revision["verification_state"],
                                       [revision["source"]],
                                       {"revision": {"claim_id": claim_id, "supersedes": revision["supersedes"]}},
                                       {"revision": {"object": new_value, "decision": decision}})
            results["fields"][predicate] = {"decision": decision,
                                            "old": old_claim["object"] if old_claim else None,
                                            "new": new_value}
        results["evidence_added"] = evidence_added
        return results

    # --------------------------------------------------------- full run
    def run(self, raw_items, mark_missing=False):
        report = {
            "status": "ok",
            "synced_at": self.now,
            "fetched": len(raw_items),
            "counts": {"create": 0, "revise": 0, "unchanged": 0, "deprecated": 0, "errors": 0},
            "changes": [],
            "errors": [],
        }
        observations = []
        for item in raw_items:
            try:
                observations.append(normalize_record(item))
            except ValueError as exc:
                report["errors"].append({"error": str(exc)})
                report["counts"]["errors"] += 1
        observations = dedupe_latest(observations)

        for obs in observations:
            try:
                plan = self.plan(obs)
                result = self.apply(plan)
                if plan["action"] == "create":
                    report["counts"]["create"] += 1
                elif plan["action"] == "revise":
                    report["counts"]["revise"] += 1
                else:
                    report["counts"]["unchanged"] += 1
                report["changes"].append(result)
            except Exception as exc:  # one bad record must not stop the sync
                report["errors"].append({"entity_id": obs.get("entity_id"), "error": str(exc)})
                report["counts"]["errors"] += 1

        if mark_missing:
            observed_ids = {obs["entity_id"] for obs in observations}
            for subject in self.synced_subjects():
                if subject not in observed_ids:
                    self._mark_deprecated(subject, report)
        return report

    def synced_subjects(self):
        return sorted({c["subject"] for c in self.store.all_claims() if c["predicate"] == "REGISTRY_NAME"})

    def _mark_deprecated(self, entity_id, report):
        if self.dry_run:
            report["counts"]["deprecated"] += 1
            report["changes"].append({"change": "missing", "entity_id": entity_id, "dry_run": True})
            return
        self.store.update_entity_lifecycle(
            entity_id, "deprecated", self.now, self.pipeline.agent_id,
            "not observed in latest registry sync",
        )
        event = {
            "event_id": "evt-registry-%s-missing" % slugify(entity_id),
            "event_type": "deprecation",
            "subject": entity_id,
            "detected_at": self.now,
            "source": "https://%s/v0/servers" % REGISTRY_ROOT,
            "confidence": 0.7,
            "affected_entities": [entity_id],
            "required_tasks": list(REQUIRED_TASKS),
            "priority": "medium",
        }
        try:
            self.store.add_event(event)
        except Exception:
            pass
        self.pipeline.record_audit("auto-accepted", "accepted", [event["source"]],
                                   {"missing": entity_id}, {"marked": "deprecated"})
        report["counts"]["deprecated"] += 1
        report["changes"].append({"change": "missing", "entity_id": entity_id})


def sync_once(store, fetcher=None, search=None, limit=20, mark_missing=False,
              now="2026-10-09", dry_run=False):
    """One scheduled sync cycle. Fetch failures leave the store untouched."""
    from sync import registry

    fetcher = fetcher or registry.fetch_servers
    try:
        document = fetcher(search=search, limit=limit)
    except (registry.FetchError, registry.AllowlistError) as exc:
        return {"status": "fetch-failed", "error": str(exc), "fetched": 0,
                "counts": {"create": 0, "revise": 0, "unchanged": 0, "deprecated": 0, "errors": 1},
                "changes": [], "errors": [{"error": str(exc)}]}
    engine = RegistrySync(store, now=now, dry_run=dry_run)
    report = engine.run(document["servers"], mark_missing=mark_missing)
    report["fetched"] = len(document["servers"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sync MCP Registry records into the SystemVirtue knowledge store")
    parser.add_argument("--db", default=str(_ROOT / "var" / "systemvirtue.db"))
    parser.add_argument("--search", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--mark-missing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval", type=int, default=86400)
    parser.add_argument("--now", default=None)
    args = parser.parse_args(argv)

    from datetime import date, datetime, timezone

    from app.server import open_store

    store = open_store(args.db)
    try:
        while True:
            now = args.now or date.today().isoformat()
            report = sync_once(store, search=args.search, limit=args.limit,
                               mark_missing=args.mark_missing, now=now, dry_run=args.dry_run)
            report["ran_at"] = datetime.now(timezone.utc).isoformat()
            out = _ROOT / "var" / "sync_report.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            # flush=True: a daemon's log must land even when killed mid-sleep
            print("sync %s: %s" % (report["status"], json.dumps(report["counts"])), flush=True)
            if report["status"] != "ok":
                print("error: %s" % report.get("error"), flush=True)
            if not args.daemon:
                break
            time.sleep(args.interval)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
