"""Scale test (REQUIREMENTS_TRACEABILITY: "Graphs become dense ->
Multi-resolution UI -> Aggregate at scale -> Scale test").

Ten copies of the seed corpus (~820 entities) must remain interactive:
search and bounded graph traversal under a strict time budget.
"""

import json
import sys
import time
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from pipeline.ingest import Pipeline  # noqa: E402
from store.db import Store  # noqa: E402
from store.index import rebuild  # noqa: E402

SEED = json.loads((_ROOT / "corpus" / "seed.json").read_text(encoding="utf-8"))
COPIES = 10
BUDGET_SECONDS = 2.0


def scaled_seed():
    evidence = list(SEED["evidence"])
    entities, claims, relationships = [], [], []
    for copy_no in range(COPIES):
        suffix = "-c%d" % copy_no
        id_map = {}
        for ent in SEED["entities"]:
            new_id = ent["entity_id"]
            if copy_no > 0:
                head, _, tail = ent["entity_id"].partition("/")
                new_id = "%s/%s%s" % (head, tail, suffix)
            id_map[ent["entity_id"]] = new_id
            clone = dict(ent, entity_id=new_id, canonical_name=ent["canonical_name"] + suffix if copy_no else ent["canonical_name"])
            entities.append(clone)
        for claim in SEED["claims"]:
            clone = dict(claim)
            if copy_no > 0:
                clone["claim_id"] = claim["claim_id"] + suffix
                clone["subject"] = id_map[claim["subject"]]
                if claim["object"] in id_map:
                    clone["object"] = id_map[claim["object"]]
            claims.append(clone)
        for rel in SEED["relationships"]:
            clone = dict(rel)
            if copy_no > 0:
                clone["relationship_id"] = rel["relationship_id"] + suffix
                clone["subject"] = id_map[rel["subject"]]
                clone["object"] = id_map[rel["object"]]
            relationships.append(clone)
    return {"evidence": evidence, "entities": entities, "claims": claims,
            "relationships": relationships, "events": []}


class TestScale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store(":memory:")
        start = time.time()
        Pipeline(cls.store).run(scaled_seed())
        cls.ingest_seconds = time.time() - start
        cls.index = rebuild(cls.store)

    def test_corpus_scaled(self):
        self.assertGreaterEqual(len(self.store.entities()), 82 * COPIES)

    def test_search_within_budget(self):
        start = time.time()
        for query in ("web search", "github", "filesystem memory", "licence", "no-such-thing"):
            self.index.search(query)
        elapsed = time.time() - start
        self.assertLess(elapsed, BUDGET_SECONDS, "5 searches took %.3fs" % elapsed)

    def test_bounded_graph_within_budget(self):
        start = time.time()
        graph = self.store.graph("mcp-server/github", depth=2)
        elapsed = time.time() - start
        self.assertLess(elapsed, BUDGET_SECONDS, "graph took %.3fs" % elapsed)
        # aggregation boundary: bounded neighbourhood, not the whole corpus
        self.assertLess(len(graph["nodes"]), 40)

    def test_ingest_is_practical(self):
        self.assertLess(self.ingest_seconds, 30.0, "10x ingest took %.1fs" % self.ingest_seconds)


if __name__ == "__main__":
    unittest.main()
