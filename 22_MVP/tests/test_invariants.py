"""Architectural invariants (SYSTEM_REQUIREMENTS.md section 12).

Each test corresponds to one numbered invariant. Where the invariant is a
structural property (e.g. "no autonomous payment authority exists") the test
scans the actual implementation; where it is behavioural (e.g. "evidence
precedes durable knowledge") the test exercises the real code path.
"""

import json
import re
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.server import KnowledgeAPI, open_store  # noqa: E402
from pipeline.ingest import ingest_seed  # noqa: E402
from store.db import KnowledgeError, Store  # noqa: E402

try:
    from tests.test_pipeline import make_claim, make_evidence  # noqa: E402
except ImportError:  # running under unittest discover
    from test_pipeline import make_claim, make_evidence  # noqa: E402

PROJECT = _ROOT.parent
CODE_SUFFIXES = (".py", ".js", ".html", ".css")


def code_files():
    for path in _ROOT.rglob("*"):
        # tests legitimately name forbidden tokens to assert their absence
        if path.suffix in CODE_SUFFIXES and path.is_file() and "tests" not in path.parts:
            yield path


def code_text():
    return "\n".join(p.read_text(encoding="utf-8") for p in code_files())


class TestInvariant1EvidencePrecedesKnowledge(unittest.TestCase):
    def test_claim_without_evidence_is_refused(self):
        store = Store(":memory:")
        with self.assertRaises(KnowledgeError):
            store.add_claim(make_claim(evidence="ev-nope"))
        with self.assertRaises(KnowledgeError):
            store.add_relationship({
                "relationship_id": "rel-nope", "subject": "a/b", "predicate": "USES",
                "object": "c/d", "evidence_id": "ev-nope", "confidence": 0.9,
                "verification_state": "accepted", "history": [],
            })


class TestInvariant2KnowledgePrecedesRecommendation(unittest.TestCase):
    def test_recommendations_come_only_from_durable_knowledge(self):
        store = Store(":memory:")
        api = KnowledgeAPI(store)
        empty = api.recommend(capability="capability/web-search")
        self.assertEqual(empty["ranking"], [])

        store2 = open_store(":memory:")
        api2 = KnowledgeAPI(store2)
        result = api2.recommend(task="task/web-research")
        self.assertTrue(result["ranking"])
        for entry in result["ranking"]:
            self.assertTrue(entry["reasons"], "every recommendation must expose reasons")
        self.assertTrue(result["uncertainty"], "every recommendation must state uncertainty")


class TestInvariant3RecommendationPrecedesExecution(unittest.TestCase):
    def test_no_execution_surface_exists(self):
        text = code_text().lower()
        for token in ("os.system", "subprocess", "exec(", "eval("):
            # usage form only: the pipeline's own deny-list names these tokens
            self.assertIsNone(
                re.search(r"(?<![\"'a-z0-9_])" + re.escape(token), text),
                "no execution surface in the MVP: found %r" % token,
            )
        # the only mutating HTTP surface is instrumentation
        server = (_ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn('"/api/events"', server)
        for route in ("/api/execute", "/api/run", "/api/write", "/api/deploy"):
            self.assertNotIn(route, server)


class TestInvariant4UserStateSeparate(unittest.TestCase):
    def test_global_store_has_no_user_tables(self):
        from store.db import SCHEMA_SQL
        lowered = SCHEMA_SQL.lower()
        for word in ("user", "account", "entitlement", "preference", "saved"):
            self.assertNotIn(word, lowered, "global knowledge store must not hold personal state")

    def test_personal_state_is_client_side(self):
        js = (_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("localStorage", js)
        server = (_ROOT / "app" / "server.py").read_text(encoding="utf-8")
        for route in ("/api/personal", "/api/saved", "/api/user"):
            self.assertNotIn(route, server)


class TestInvariant5ExternalContentUntrusted(unittest.TestCase):
    def test_ui_never_executes_injected_markup(self):
        for name in ("app.js", "index.html", "style.css"):
            text = (_ROOT / "app" / "static" / name).read_text(encoding="utf-8")
            for token in ("innerHTML", "document.write", "eval("):
                self.assertIsNone(
                    re.search(r"(?<![\"'a-z0-9_-])" + re.escape(token), text),
                    "%s must not use %s" % (name, token),
                )

    def test_hostile_claim_is_rejected_by_pipeline(self):
        store = Store(":memory:")
        report = ingest_seed(store, _ROOT / "corpus" / "seed.json")
        # seed is clean; inject hostility through the pipeline directly
        from pipeline.ingest import Pipeline
        pipeline = Pipeline(store, now="2026-10-09")
        hostile = pipeline.run({
            "evidence": [make_evidence()],
            "entities": [],
            "claims": [make_claim(obj="javascript:alert(document.cookie)")],
            "relationships": [],
            "events": [],
        })
        self.assertEqual(hostile["decisions"][0]["decision"], "rejected")


class TestInvariant6AgentsReplaceable(unittest.TestCase):
    def test_authority_lives_in_contract_not_code(self):
        from pipeline.ingest import AGENT_CONTRACT_SCHEMA, RESEARCH_CONTRACT
        self.assertEqual(set(AGENT_CONTRACT_SCHEMA["required"]) - set(RESEARCH_CONTRACT), set())
        store = Store(":memory:")
        report = ingest_seed(store, _ROOT / "corpus" / "seed.json", agent_id="another-agent")
        self.assertGreater(report["counts"]["auto-accepted"], 0)


class TestInvariant7DeterministicPolicyAuthoritative(unittest.TestCase):
    def test_policy_is_pure_and_versioned(self):
        from pipeline.ingest import POLICY_VERSION, policy_decision
        ctx = {"structural_errors": [], "freshness": "fresh", "authoritative": True,
               "confidence": 0.9, "corroborators": 0, "contradictions": [], "risk": "low"}
        results = {policy_decision(dict(ctx)) for _ in range(5)}
        self.assertEqual(len(results), 1)
        self.assertEqual(POLICY_VERSION, "policy-v1")


class TestInvariant8NoPaymentAuthority(unittest.TestCase):
    def test_no_payment_surface_in_code(self):
        forbidden = ("stripe", "paypal", "billing", "credit card", "payment", "checkout", "card number")
        text = code_text().lower()
        for token in forbidden:
            self.assertNotIn(token, text, "found forbidden financial token %r" % token)


class TestInvariant9DecisionsReconstructable(unittest.TestCase):
    def test_audit_chain_reconstructs_decisions(self):
        store = open_store(":memory:")
        api = KnowledgeAPI(store)
        records = store.audit_records()
        self.assertGreater(len(records), 0)
        for record in records:
            self.assertTrue(record["input_hash"].startswith("sha256:"))
            self.assertTrue(record["output_hash"].startswith("sha256:"))
            self.assertTrue(record["policy_version"])
        # committed claims carry history entries recording their decision
        for claim in store.all_claims():
            self.assertTrue(claim["history"], claim["claim_id"])
            self.assertTrue(claim["policy_state"])


class TestInvariant10VisualisationNotMandatory(unittest.TestCase):
    def test_semantic_equivalent_exists_and_graph_is_decorative(self):
        html = (_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        js = (_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Relationship view (optional)", js)
        self.assertIn("aria-hidden", js)
        self.assertIn("Relationships (text equivalent of the graph)", js)
        self.assertIn('role: "list"', js)

    def test_relationship_data_available_as_text(self):
        store = open_store(":memory:")
        api = KnowledgeAPI(store)
        detail = api.entity_detail("mcp-server/github")
        self.assertTrue(detail["relationships"], "text relationship list must have data")
        graph = store.graph("mcp-server/github", depth=1)
        self.assertTrue(graph["edges"])

    def test_aggregate_views_have_text_alternatives(self):
        """The Ecosystem map and Changes & freshness views: charts are
        decorative (aria-hidden) and each view carries a table or list with
        the same information. Graph depth/zoom controls are keyboard-reachable
        form controls with a text extent readout."""
        html = (_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        js = (_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="view-map"', html)
        self.assertIn('id="view-changes"', html)

        map_src = js.split("function renderMap()")[1].split("function browseType")[0]
        changes_src = js.split("function renderChanges()")[1]

        # charts are decorative; the tables/lists below them are authoritative
        self.assertIn('svg.setAttribute("aria-hidden", "true")', js)
        self.assertIn("barChart(", map_src)
        self.assertIn("barChart(", changes_src)
        self.assertIn('el("table"', map_src)
        self.assertIn("scope", map_src)  # semantic row/column headers
        self.assertIn('role: "list"', changes_src)
        self.assertIn('el("table"', changes_src)

        # relationship graph: depth selector + zoom buttons + text readout
        self.assertIn('id: "graph-depth"', js)
        self.assertIn("zoomGraph", js)
        self.assertIn("Extent: ", js)

        # semantic-zoom studio: breadcrumbs, contextual inspector, and the
        # authoritative text-equivalent table for the map
        self.assertIn('id="map-crumbs-list"', html)
        self.assertIn('id="map-inspector"', html)
        self.assertIn('id="map-canvas-core"', html)
        self.assertIn("Map text equivalent", js)
        self.assertIn('"aria-current": "location"', js)


class TestProvenanceAudit(unittest.TestCase):
    """Provenance audit (REQUIREMENTS_TRACEABILITY): 100% of displayed claims
    resolve to an evidence record with source and date."""

    def test_every_displayed_claim_has_evidence(self):
        store = open_store(":memory:")
        api = KnowledgeAPI(store)
        entities = store.entities()
        self.assertGreater(len(entities), 50)
        checked = 0
        for ent in entities:
            detail = api.entity_detail(ent["entity_id"])
            for item in detail["claims"]:
                checked += 1
                ev = item["evidence"]
                self.assertIsNotNone(ev, item["claim"]["claim_id"])
                self.assertTrue(ev["source"].startswith("https://"), item["claim"]["claim_id"])
                self.assertTrue(ev["retrieved_at"], item["claim"]["claim_id"])
        self.assertGreater(checked, 80)


if __name__ == "__main__":
    unittest.main()
