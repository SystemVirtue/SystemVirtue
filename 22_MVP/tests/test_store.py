import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from store.db import KnowledgeError, Store  # noqa: E402
from store.index import rebuild, tokenize  # noqa: E402

EV = {
    "evidence_id": "ev-store-one",
    "source": "https://example.org/a",
    "source_type": "official-docs",
    "source_root": "example.org",
    "title": "Page A",
    "retrieved_at": "2026-10-09",
    "content_hash": "sha256:" + "b" * 64,
    "derived_from": None,
    "excerpt": "excerpt a",
}

ENT_A = {
    "entity_id": "mcp-server/alpha", "entity_type": "mcp_server", "canonical_name": "Alpha Server",
    "aliases": ["alpha"], "source_ids": {}, "evidence_ids": ["ev-store-one"],
    "lifecycle_state": "active", "valid_from": "2026-10-09", "valid_until": None, "history": [],
}
ENT_B = {
    "entity_id": "tool/beta", "entity_type": "tool", "canonical_name": "beta_tool",
    "aliases": [], "source_ids": {}, "evidence_ids": ["ev-store-one"],
    "lifecycle_state": "active", "valid_from": "2026-10-09", "valid_until": None, "history": [],
}

CLAIM_V1 = {
    "claim_id": "claim-version-one", "subject": "mcp-server/alpha", "predicate": "DESCRIPTION",
    "object": "original description", "source": "https://example.org/a", "source_type": "official-docs",
    "evidence": "ev-store-one", "discovered_at": "2026-06-01", "verified_at": "2026-06-01",
    "valid_from": "2026-06-01", "valid_until": None, "agent_id": "test-agent", "model_id": "test",
    "confidence": 0.9, "freshness": "fresh", "verification_state": "accepted", "contradictions": [],
    "policy_state": "auto-accepted", "history": [], "supersedes": None, "superseded_by": None,
}

REL = {
    "relationship_id": "rel-alpha-exposes-beta", "subject": "mcp-server/alpha", "predicate": "EXPOSES",
    "object": "tool/beta", "evidence_id": "ev-store-one", "confidence": 0.9,
    "verification_state": "accepted", "valid_from": "2026-10-09", "valid_until": None, "history": [],
}


def seeded_store():
    store = Store(":memory:")
    store.add_evidence(EV)
    store.add_entity(ENT_A)
    store.add_entity(ENT_B)
    store.add_claim(dict(CLAIM_V1))
    store.add_relationship(dict(REL))
    return store


class TestAppendOnlyHistory(unittest.TestCase):
    """Change-history test (REQUIREMENTS_TRACEABILITY)."""

    def test_supersede_preserves_old_content(self):
        store = seeded_store()
        revision = dict(CLAIM_V1, claim_id="claim-version-two", object="revised description",
                        discovered_at="2026-10-01", supersedes="claim-version-one")
        store.supersede_claim("claim-version-one", revision)

        old = store.claim("claim-version-one")
        new = store.claim("claim-version-two")

        # old content untouched
        self.assertEqual(old["object"], "original description")
        self.assertEqual(old["superseded_by"], "claim-version-two")
        # history records the change
        self.assertEqual(old["history"][-1]["action"], "superseded")
        self.assertEqual(new["supersedes"], "claim-version-one")

    def test_current_claims_exclude_superseded(self):
        store = seeded_store()
        revision = dict(CLAIM_V1, claim_id="claim-version-two", object="revised",
                        supersedes="claim-version-one")
        store.supersede_claim("claim-version-one", revision)
        current = store.claims_for("mcp-server/alpha")
        self.assertEqual([c["claim_id"] for c in current], ["claim-version-two"])
        all_of_them = store.claims_for("mcp-server/alpha", include_superseded=True)
        self.assertEqual(len(all_of_them), 2)

    def test_double_supersede_refused(self):
        store = seeded_store()
        store.supersede_claim("claim-version-one",
                              dict(CLAIM_V1, claim_id="claim-version-two", supersedes="claim-version-one"))
        with self.assertRaises(KnowledgeError):
            store.supersede_claim("claim-version-one",
                                  dict(CLAIM_V1, claim_id="claim-version-three"))

    def test_duplicate_claim_id_refused(self):
        store = seeded_store()
        with self.assertRaises(KnowledgeError):
            store.add_claim(dict(CLAIM_V1))

    def test_relationship_requires_evidence(self):
        store = seeded_store()
        with self.assertRaises(KnowledgeError):
            store.add_relationship(dict(REL, relationship_id="rel-orphan", evidence_id="ev-missing"))


class TestQueries(unittest.TestCase):
    def test_graph_is_bounded(self):
        store = seeded_store()
        graph = store.graph("mcp-server/alpha", depth=1)
        ids = {n["entity_id"] for n in graph["nodes"]}
        self.assertEqual(ids, {"mcp-server/alpha", "tool/beta"})
        self.assertEqual(len(graph["edges"]), 1)

    def test_compare_returns_claims_and_relationships(self):
        store = seeded_store()
        items = store.compare(["mcp-server/alpha", "tool/beta"])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["claims"][0]["claim_id"], "claim-version-one")
        self.assertEqual(len(items[0]["relationships"]), 1)

    def test_evidence_is_immutable_reference(self):
        store = seeded_store()
        ev = store.evidence("ev-store-one")
        self.assertEqual(ev["source"], "https://example.org/a")
        self.assertEqual(ev["source_root"], "example.org")


class TestDerivedIndex(unittest.TestCase):
    """Indexes are derived: rebuildable from canonical knowledge."""

    def test_tokenize(self):
        self.assertEqual(tokenize("GitHub MCP-Server!"), ["github", "mcp", "server"])

    def test_search_by_name_and_alias(self):
        store = seeded_store()
        index = rebuild(store)
        self.assertIn("mcp-server/alpha", index.search("alpha"))
        self.assertIn("tool/beta", index.search("beta_tool"))

    def test_rebuild_is_idempotent(self):
        store = seeded_store()
        first = rebuild(store).postings
        second = rebuild(store).postings
        self.assertEqual(first, second)

    def test_description_text_is_indexed(self):
        store = seeded_store()
        index = rebuild(store)
        self.assertIn("mcp-server/alpha", index.search("original description"))


if __name__ == "__main__":
    unittest.main()
