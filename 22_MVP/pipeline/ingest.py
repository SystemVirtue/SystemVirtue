"""Knowledge verification pipeline (VERIFICATION_PIPELINE.md).

    DISCOVER -> EXTRACT -> NORMALISE -> CORROBORATE -> CLASSIFY -> VERIFY
    -> CHECK CONTRADICTIONS -> ASSESS FRESHNESS -> POLICY DECISION
    -> COMMIT -> AUDIT

Policy is deterministic and authoritative (invariant 7). Agents supply
claims; they never decide acceptance themselves. "Ten websites repeating
one source are still one source": corroboration counts independent source
roots, and derived evidence inherits the root of what it copied.
"""

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schemas.validate import assert_valid, validate  # noqa: E402

POLICY_VERSION = "policy-v1"
DEFAULT_AGENT = "research-agent-v1"
DEFAULT_MODEL = "manual-curation"

AUTHORITATIVE_SOURCE_TYPES = {"spec", "official-docs", "official-repo", "registry"}

MALICIOUS_PATTERNS = ("<script", "javascript:", "onerror=", "eval(", "${jndi")

HIGH_RISK_KEYWORDS = ("SECURITY", "PERMISSION", "CREDENTIAL")
MEDIUM_RISK_PREDICATES = {"LICENSED_UNDER", "AVAILABLE_THROUGH", "REQUIRES", "PRICE", "QUOTA"}

SINGLE_VALUED_PREDICATES = {"DESCRIPTION", "LICENSED_UNDER", "HOSTED_BY", "AVAILABLE_THROUGH"}

FRESH_DAYS = 180
STALE_DAYS = 365


def load_schema(name):
    return json.loads((_ROOT / "schemas" / name).read_text(encoding="utf-8"))


CLAIM_SCHEMA = load_schema("claim.schema.json")
EVIDENCE_SCHEMA = load_schema("evidence.schema.json")
ENTITY_SCHEMA = load_schema("entity.schema.json")
RELATIONSHIP_SCHEMA = load_schema("relationship.schema.json")
EVENT_SCHEMA = load_schema("event.schema.json")
AUDIT_SCHEMA = load_schema("audit_record.schema.json")
AGENT_CONTRACT_SCHEMA = load_schema("agent_contract.schema.json")

# The research agent's contract (SYSTEM_REQUIREMENTS.md section 8).
RESEARCH_CONTRACT = {
    "task_id": "task-ingest-seed-corpus",
    "role": "research",
    "objective": "Extract and verify claims from curated official sources into the knowledge store",
    "inputs": ["22_MVP/corpus/seed.json"],
    "allowed_tools": ["http-fetch", "json-parse", "schema-validate"],
    "allowed_sources": ["modelcontextprotocol.io", "registry.modelcontextprotocol.io", "github.com"],
    "permissions": ["knowledge.write", "audit.write"],
    "risk_class": "low",
    "deadline": None,
    "required_evidence": "every claim must reference an immutable evidence record",
    "verification_policy": "auto-accept-low-risk",
    "output_schema": "schemas/claim.schema.json",
    "fallback": "escalate to human review; never fabricate",
    "rollback": "revert to previous claim revision via supersede chain",
}


def hash_obj(obj):
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def is_authoritative(source_type):
    return source_type in AUTHORITATIVE_SOURCE_TYPES


def assess_freshness(discovered_at, now):
    """Freshness is assessed from evidence age, not from agent confidence."""
    from datetime import date

    y, m, d = int(discovered_at[:4]), int(discovered_at[5:7]), int(discovered_at[8:10])
    ny, nm, nd = int(now[:4]), int(now[5:7]), int(now[8:10])
    age_days = (date(ny, nm, nd) - date(y, m, d)).days
    if age_days > STALE_DAYS:
        return "stale"
    if age_days > FRESH_DAYS:
        return "aging"
    return "fresh"


def classify_risk(predicate):
    upper = predicate.upper()
    if any(k in upper for k in HIGH_RISK_KEYWORDS):
        return "high"
    if predicate in MEDIUM_RISK_PREDICATES:
        return "medium"
    return "low"


def is_malicious(text):
    lowered = text.lower()
    return any(pattern in lowered for pattern in MALICIOUS_PATTERNS)


def normalise(claim):
    """NORMALISE stage: structural validation plus untrusted-content checks
    (invariant 5: external content remains untrusted)."""
    errors = validate(claim, CLAIM_SCHEMA)
    for field in ("subject", "predicate", "object"):
        if is_malicious(str(claim.get(field, ""))):
            errors.append("malicious content pattern in %s" % field)
    return errors


def independent_root(evidence_id, evidence_map):
    """Follow derived_from to the root so copied pages collapse to one source."""
    seen = set()
    current = evidence_id
    while current and current not in seen:
        seen.add(current)
        ev = evidence_map.get(current)
        if ev is None:
            break
        if ev.get("derived_from"):
            current = ev["derived_from"]
        else:
            return ev["source_root"]
    ev = evidence_map.get(evidence_id)
    return ev["source_root"] if ev else "unknown"


def corroborate(claim, evidence_map, prior_claims):
    """Count INDEPENDENT sources supporting the same statement."""
    roots = set()
    key = (claim["subject"], claim["predicate"], claim["object"].strip().lower())
    for other in prior_claims:
        other_key = (other["subject"], other["predicate"], other["object"].strip().lower())
        if other_key == key:
            roots.add(independent_root(other["evidence"], evidence_map))
    roots.add(independent_root(claim["evidence"], evidence_map))
    return roots


def check_contradictions(claim, prior_claims):
    """Contradictory evidence is preserved and linked, never overwritten (FR-K07)."""
    if claim["predicate"] not in SINGLE_VALUED_PREDICATES:
        return []
    conflicts = []
    for other in prior_claims:
        if other.get("superseded_by"):
            continue
        if (
            other["subject"] == claim["subject"]
            and other["predicate"] == claim["predicate"]
            and other["object"].strip().lower() != claim["object"].strip().lower()
        ):
            conflicts.append(other["claim_id"])
    return conflicts


def policy_decision(ctx):
    """Deterministic acceptance policy (VERIFICATION_PIPELINE.md).

    auto-accept      low-risk, high-confidence, authoritative source
    conditional-accept strong evidence but ambiguity remains
    escalate         conflicting authoritative sources
    reject           unsupported, malicious, stale or structurally invalid
    """
    if ctx["structural_errors"]:
        return "rejected", "structurally invalid: %s" % "; ".join(ctx["structural_errors"])
    if ctx["freshness"] == "stale":
        return "rejected", "stale evidence (older than %d days)" % STALE_DAYS
    if ctx["contradictions"]:
        if ctx["authoritative"]:
            return "escalated", "conflicts with established claims %s" % ctx["contradictions"]
        return "rejected", "non-authoritative claim contradicts established claims %s" % ctx["contradictions"]
    if ctx["risk"] == "high":
        if ctx["confidence"] >= 0.6:
            return "conditional-accepted", "high-risk predicate requires human confirmation"
        return "rejected", "high-risk claim with low confidence"
    if ctx["authoritative"] and ctx["confidence"] >= 0.8:
        return "auto-accepted", "authoritative source, high confidence, low risk"
    if ctx["confidence"] >= 0.6 and (ctx["authoritative"] or ctx["corroborators"] >= 1):
        return "conditional-accepted", "supportive evidence but ambiguity remains"
    return "rejected", "unsupported: no authoritative source and insufficient corroboration"


VERIFICATION_BY_POLICY = {
    "auto-accepted": "accepted",
    "conditional-accepted": "conditional",
    "escalated": "escalated",
    "rejected": "rejected",
}


class Pipeline:
    def __init__(self, store, agent_id=DEFAULT_AGENT, model_id=DEFAULT_MODEL, now="2026-10-09"):
        self.store = store
        self.agent_id = agent_id
        self.model_id = model_id
        self.now = now
        # continue the audit sequence when a store is fed by several pipelines
        self.action_seq = len(store.audit_records())

    # ---- AUDIT stage -------------------------------------------------
    def _audit(self, decision, verification, sources, input_obj, output_obj):
        self.action_seq += 1
        record = {
            "action_id": "act-%04d" % self.action_seq,
            "agent_id": self.agent_id,
            "agent_role": "research",
            "model": self.model_id,
            "model_version": "1",
            "policy_version": POLICY_VERSION,
            "prompt_configuration": "curated-ingest",
            "tools": ["http-fetch", "json-parse", "schema-validate"],
            "sources": sources,
            "input_hash": hash_obj(input_obj),
            "output_hash": hash_obj(output_obj),
            "decision": decision,
            "verification": verification,
            "timestamp": "%sT00:00:00Z" % self.now,
        }
        assert_valid(record, AUDIT_SCHEMA, "audit record")
        self.store.add_audit(record)
        return record

    def record_audit(self, decision, verification, sources, input_obj, output_obj):
        """Public audit hook for adjacent pipelines (e.g. registry sync)."""
        return self._audit(decision, verification, sources, input_obj, output_obj)

    # ---- full pipeline over a seed document ---------------------------
    def run(self, seed):
        report = {
            "policy_version": POLICY_VERSION,
            "agent_id": self.agent_id,
            "processed_at": self.now,
            "counts": {},
            "decisions": [],
            "contradictions": [],
            "errors": [],
        }

        # DISCOVER + EXTRACT (the curated corpus is the discovery surface)
        evidence_list = seed.get("evidence", [])
        entities = seed.get("entities", [])
        claims = seed.get("claims", [])
        relationships = seed.get("relationships", [])
        events = seed.get("events", [])

        # Evidence first: evidence precedes durable knowledge (invariant 1)
        evidence_map = {}
        for ev in evidence_list:
            errors = validate(ev, EVIDENCE_SCHEMA)
            if errors:
                report["errors"].append({"evidence_id": ev.get("evidence_id"), "errors": errors})
                continue
            self.store.add_evidence(ev)
            evidence_map[ev["evidence_id"]] = ev

        for ent in entities:
            errors = validate(ent, ENTITY_SCHEMA)
            if errors:
                report["errors"].append({"entity_id": ent.get("entity_id"), "errors": errors})
                continue
            self.store.add_entity(ent)

        committed = []
        counts = {"claims_total": 0, "auto-accepted": 0, "conditional-accepted": 0, "escalated": 0, "rejected": 0}

        for raw_claim in claims:
            counts["claims_total"] += 1
            claim = dict(raw_claim)

            # NORMALISE
            structural_errors = normalise(claim)

            # CORROBORATE
            roots = corroborate(claim, evidence_map, committed)

            # CLASSIFY
            risk = classify_risk(claim["predicate"])

            # VERIFY + CHECK CONTRADICTIONS + FRESHNESS
            contradictions = check_contradictions(claim, committed)
            freshness = assess_freshness(claim["discovered_at"], self.now)
            authoritative = is_authoritative(claim.get("source_type", ""))
            conf = float(claim.get("confidence", 0.0))

            ctx = {
                "structural_errors": structural_errors,
                "freshness": freshness,
                "authoritative": authoritative,
                "confidence": conf,
                "corroborators": len(roots) - 1,
                "contradictions": contradictions,
                "risk": risk,
            }

            # POLICY DECISION
            decision, rationale = policy_decision(ctx)
            claim["freshness"] = freshness
            claim["policy_state"] = decision
            claim["verification_state"] = VERIFICATION_BY_POLICY[decision]
            claim["contradictions"] = contradictions
            claim.setdefault("history", []).append(
                {"at": self.now, "agent_id": self.agent_id, "action": "policy-decision", "detail": rationale}
            )

            counts[decision] += 1
            report["decisions"].append({"claim_id": claim["claim_id"], "decision": decision, "rationale": rationale})
            if contradictions:
                report["contradictions"].append({"claim_id": claim["claim_id"], "conflicts_with": contradictions})

            # COMMIT (rejected claims never enter durable knowledge)
            if decision != "rejected":
                self.store.add_claim(claim)
                committed.append(claim)

            # AUDIT (every decision is attributable and reconstructable)
            self._audit(
                decision,
                claim["verification_state"],
                [claim["source"]],
                {"claim": raw_claim},
                {"claim": claim},
            )

        rel_counts = {"accepted": 0, "conditional": 0, "rejected": 0}
        for rel in relationships:
            errors = validate(rel, RELATIONSHIP_SCHEMA)
            if errors:
                report["errors"].append({"relationship_id": rel.get("relationship_id"), "errors": errors})
                rel_counts["rejected"] += 1
                continue
            if rel["confidence"] >= 0.8:
                state = "accepted"
            elif rel["confidence"] >= 0.6:
                state = "conditional"
            else:
                state = "rejected"
            rel_counts[state] += 1
            if state != "rejected":
                rel = dict(rel)
                rel["verification_state"] = state
                self.store.add_relationship(rel)

        for event in events:
            errors = validate(event, EVENT_SCHEMA)
            if errors:
                report["errors"].append({"event_id": event.get("event_id"), "errors": errors})
                continue
            self.store.add_event(event)

        counts["entities"] = len(entities)
        counts["evidence"] = len(evidence_map)
        counts["relationships_accepted"] = rel_counts["accepted"]
        counts["relationships_conditional"] = rel_counts["conditional"]
        counts["events"] = len(events)
        report["counts"] = counts
        return report


def ingest_seed(store, seed_path, **kwargs):
    seed = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    pipeline = Pipeline(store, **kwargs)
    return pipeline.run(seed)
