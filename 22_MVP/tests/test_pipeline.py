import copy
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from pipeline.ingest import (  # noqa: E402
    Pipeline,
    assess_freshness,
    check_contradictions,
    classify_risk,
    corroborate,
    policy_decision,
)
from store.db import KnowledgeError, Store  # noqa: E402


def make_evidence(eid="ev-test-one", root="example.org", source_type="official-docs", derived_from=None):
    return {
        "evidence_id": eid,
        "source": "https://%s/page" % root,
        "source_type": source_type,
        "source_root": root,
        "title": "Test page %s" % eid,
        "retrieved_at": "2026-10-09",
        "content_hash": "sha256:" + "a" * 64,
        "derived_from": derived_from,
        "excerpt": "excerpt for %s" % eid,
    }


def make_claim(cid="claim-test-one", subject="mcp-server/test", predicate="DESCRIPTION",
               obj="a test description", evidence="ev-test-one", source_type="official-docs",
               confidence=0.9, discovered_at="2026-10-09", verified_at=None):
    return {
        "claim_id": cid,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source": "https://example.org/page",
        "source_type": source_type,
        "evidence": evidence,
        "discovered_at": discovered_at,
        "verified_at": verified_at or discovered_at,
        "valid_from": discovered_at,
        "valid_until": None,
        "agent_id": "test-agent",
        "model_id": "test-model",
        "confidence": confidence,
        "freshness": "fresh",
        "verification_state": "conditional",
        "contradictions": [],
        "policy_state": "conditional-accepted",
        "history": [],
        "supersedes": None,
        "superseded_by": None,
    }


def run_claims(claims, evidence_list=None, entities=None, now="2026-10-09", agent_id="test-agent"):
    store = Store(":memory:")
    evidence_list = evidence_list or [make_evidence()]
    pipeline = Pipeline(store, agent_id=agent_id, now=now)
    report = pipeline.run({
        "evidence": evidence_list,
        "entities": entities or [],
        "claims": claims,
        "relationships": [],
        "events": [],
    })
    return store, report


class TestPolicyMatrix(unittest.TestCase):
    def test_auto_accept_authoritative_high_confidence(self):
        store, report = run_claims([make_claim(confidence=0.9)])
        self.assertEqual(report["decisions"][0]["decision"], "auto-accepted")
        self.assertEqual(store.claim("claim-test-one")["verification_state"], "accepted")

    def test_conditional_ambiguous_confidence(self):
        _, report = run_claims([make_claim(confidence=0.7)])
        self.assertEqual(report["decisions"][0]["decision"], "conditional-accepted")

    def test_reject_unsupported_third_party(self):
        store, report = run_claims([make_claim(source_type="user-report", confidence=0.5)])
        self.assertEqual(report["decisions"][0]["decision"], "rejected")
        self.assertIsNone(store.claim("claim-test-one"))

    def test_reject_stale(self):
        _, report = run_claims([make_claim(discovered_at="2020-01-01", verified_at="2020-01-01")])
        self.assertEqual(report["decisions"][0]["decision"], "rejected")
        self.assertIn("stale", report["decisions"][0]["rationale"])

    def test_high_risk_never_auto_accepts(self):
        _, report = run_claims([make_claim(predicate="SECURITY_POLICY", confidence=0.95)])
        self.assertEqual(report["decisions"][0]["decision"], "conditional-accepted")

    def test_freshness_assessment(self):
        self.assertEqual(assess_freshness("2026-10-01", "2026-10-09"), "fresh")
        self.assertEqual(assess_freshness("2026-03-01", "2026-10-09"), "aging")
        self.assertEqual(assess_freshness("2024-01-01", "2026-10-09"), "stale")

    def test_risk_classification(self):
        self.assertEqual(classify_risk("SECURITY_POLICY"), "high")
        self.assertEqual(classify_risk("PERMISSION_GRANT"), "high")
        self.assertEqual(classify_risk("LICENSED_UNDER"), "medium")
        self.assertEqual(classify_risk("DESCRIPTION"), "low")


class TestErrorInjection(unittest.TestCase):
    """External content is untrusted (invariant 5)."""

    def test_script_injection_rejected(self):
        store, report = run_claims([make_claim(obj='<script>alert(1)</script>')])
        self.assertEqual(report["decisions"][0]["decision"], "rejected")
        self.assertIn("malicious", report["decisions"][0]["rationale"])
        self.assertIsNone(store.claim("claim-test-one"))

    def test_structurally_invalid_rejected(self):
        bad = make_claim()
        del bad["confidence"]
        store, report = run_claims([bad])
        self.assertEqual(report["decisions"][0]["decision"], "rejected")
        self.assertIsNone(store.claim("claim-test-one"))

    def test_rejected_claims_never_enter_durable_knowledge(self):
        store, report = run_claims([
            make_claim(cid="claim-bad-one", obj="<script>x</script>"),
            make_claim(cid="claim-good-one", obj="fine"),
        ])
        self.assertIsNone(store.claim("claim-bad-one"))
        self.assertIsNotNone(store.claim("claim-good-one"))


class TestContradictions(unittest.TestCase):
    def test_conflicting_authoritative_claims_escalate_and_are_preserved(self):
        ev = [make_evidence()]
        first = make_claim(cid="claim-lic-one", predicate="LICENSED_UNDER", obj="licence/mit")
        second = make_claim(cid="claim-lic-two", predicate="LICENSED_UNDER", obj="licence/gpl-3-0")
        store, report = run_claims([first, second], evidence_list=ev)
        self.assertEqual(report["decisions"][1]["decision"], "escalated")
        # FR-K07: contradictory evidence preserved, never overwritten
        self.assertIsNotNone(store.claim("claim-lic-one"))
        self.assertIsNotNone(store.claim("claim-lic-two"))
        self.assertEqual(store.claim("claim-lic-two")["contradictions"], ["claim-lic-one"])

    def test_description_coexistence_not_contradiction(self):
        first = make_claim(cid="claim-desc-one", predicate="DESCRIPTION", obj="one wording")
        second = make_claim(cid="claim-desc-two", predicate="DESCRIPTION", obj="another wording")
        # DESCRIPTION is single-valued: different wording IS a contradiction pair
        self.assertEqual(check_contradictions(second, [first]), ["claim-desc-one"])

    def test_multi_valued_predicates_do_not_contradict(self):
        first = make_claim(cid="claim-cap-one", predicate="CAPABLE_OF", obj="capability/a")
        second = make_claim(cid="claim-cap-two", predicate="CAPABLE_OF", obj="capability/b")
        self.assertEqual(check_contradictions(second, [first]), [])


class TestCorroboration(unittest.TestCase):
    def test_ten_copied_pages_are_one_source(self):
        evidence = [
            make_evidence("ev-root", root="origin.example"),
            make_evidence("ev-copy-a", root="site-a.example", derived_from="ev-root"),
            make_evidence("ev-copy-b", root="site-b.example", derived_from="ev-root"),
        ]
        emap = {e["evidence_id"]: e for e in evidence}
        prior = [
            make_claim(cid="claim-prior-a", evidence="ev-copy-a", obj="same statement"),
            make_claim(cid="claim-prior-b", evidence="ev-copy-b", obj="same statement"),
        ]
        incoming = make_claim(cid="claim-incoming", evidence="ev-root", obj="same statement")
        roots = corroborate(incoming, emap, prior)
        # all three collapse to origin.example: zero independent corroborators
        self.assertEqual(roots, {"origin.example"})

    def test_independent_roots_count(self):
        evidence = [
            make_evidence("ev-one", root="one.example"),
            make_evidence("ev-two", root="two.example"),
        ]
        emap = {e["evidence_id"]: e for e in evidence}
        prior = [make_claim(cid="claim-prior", evidence="ev-two", obj="same statement")]
        incoming = make_claim(cid="claim-incoming", evidence="ev-one", obj="same statement")
        roots = corroborate(incoming, emap, prior)
        self.assertEqual(roots, {"one.example", "two.example"})


class TestDeterminismAndAudit(unittest.TestCase):
    def test_policy_decision_is_deterministic(self):
        ctx = {
            "structural_errors": [], "freshness": "fresh", "authoritative": True,
            "confidence": 0.85, "corroborators": 0, "contradictions": [], "risk": "low",
        }
        self.assertEqual(policy_decision(ctx), policy_decision(copy.deepcopy(ctx)))

    def test_every_decision_is_audited(self):
        store, report = run_claims([
            make_claim(cid="claim-good-one", obj="fine"),
            make_claim(cid="claim-bad-one", obj="<script>x</script>"),
        ])
        records = store.audit_records()
        self.assertEqual(len(records), 2)
        decisions = sorted(r["decision"] for r in records)
        self.assertEqual(decisions, ["auto-accepted", "rejected"])
        for record in records:
            self.assertTrue(record["input_hash"].startswith("sha256:"))
            self.assertTrue(record["output_hash"].startswith("sha256:"))

    def test_evidence_precedes_durable_knowledge(self):
        store = Store(":memory:")
        with self.assertRaises(KnowledgeError):
            store.add_claim(make_claim(evidence="ev-does-not-exist"))

    def test_agents_are_replaceable(self):
        store, report = run_claims([make_claim()], agent_id="replacement-agent-v2")
        self.assertEqual(report["decisions"][0]["decision"], "auto-accepted")
        self.assertEqual(store.audit_records()[0]["agent_id"], "replacement-agent-v2")


if __name__ == "__main__":
    unittest.main()
