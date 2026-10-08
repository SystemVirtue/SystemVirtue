"""End-to-end over real HTTP: the app server, the baseline directory,
instrumented events, and metrics aggregation on the resulting log."""

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import app.server as app_server  # noqa: E402
import validation.baseline.baseline_server as baseline_server  # noqa: E402

sys.path.insert(0, str(_ROOT / "validation"))
import metrics  # noqa: E402


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.event_log = Path(cls.tmp.name) / "events.jsonl"
        cls._old_log = app_server.EVENT_LOG
        app_server.EVENT_LOG = str(cls.event_log)

        cls.app_srv, cls.app_api = app_server.create_server(port=0, db_path=":memory:")
        cls.base_srv, _ = baseline_server.create_server(port=0, db_path=":memory:")
        cls.app = "http://127.0.0.1:%d" % cls.app_srv.server_address[1]
        cls.base = "http://127.0.0.1:%d" % cls.base_srv.server_address[1]
        for srv in (cls.app_srv, cls.base_srv):
            threading.Thread(target=srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.app_srv.shutdown()
        cls.base_srv.shutdown()
        app_server.EVENT_LOG = cls._old_log
        cls.tmp.cleanup()

    def get_json(self, path):
        with urlopen(self.app + path, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_html(self, path):
        with urlopen(self.base + path, timeout=10) as resp:
            return resp.read().decode("utf-8")

    def post_event(self, base, api, event):
        req = Request(base + api, data=json.dumps(event).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_01_health(self):
        data = self.get_json("/api/health")
        self.assertEqual(data["status"], "ok")
        self.assertGreater(data["entities"], 50)

    def test_02_search(self):
        data = self.get_json("/api/search?q=web%20search")
        self.assertGreater(data["total"], 0)
        self.assertIn("entity_id", data["results"][0])
        # FR-S04 facets: type, capability, licence
        typed = self.get_json("/api/search?q=github&type=mcp_server")
        self.assertTrue(typed["results"])
        self.assertTrue(all(r["entity_type"] == "mcp_server" for r in typed["results"]))
        capable = self.get_json("/api/search?capability=capability/web-search")
        self.assertTrue(capable["results"])
        licensed = self.get_json("/api/search?licence=licence/mit")
        self.assertTrue(licensed["results"])

    def test_03_entity_provenance_over_http(self):
        data = self.get_json("/api/entity/mcp-server/github")
        self.assertTrue(data["claims"])
        for item in data["claims"]:
            ev = item["evidence"]
            self.assertIsNotNone(ev)
            self.assertTrue(ev["source"].startswith("https://"))
            self.assertTrue(ev["retrieved_at"])
        self.assertTrue(data["relationships"])
        self.assertIn(data["freshness"]["state"], ("fresh", "aging", "stale", "unknown"))

    def test_04_explore_cites_claims(self):
        data = self.get_json("/api/explore?q=What%20can%20the%20GitHub%20MCP%20Server%20do")
        self.assertTrue(data["answer"])
        self.assertTrue(data["uncertainty"])
        self.assertTrue(data["citations"])

    def test_05_recommend_exposes_reasons(self):
        data = self.get_json("/api/recommend?task=task/web-research")
        self.assertTrue(data["ranking"])
        self.assertTrue(data["ranking"][0]["reasons"])
        self.assertTrue(data["uncertainty"])
        self.assertIn("alternatives", data)

    def test_06_baseline_is_conventional(self):
        home = self.get_html("/")
        self.assertIn("Directory", home)
        results = self.get_html("/search?q=web")
        self.assertIn("result", results)
        page = self.get_html("/entity/mcp-server/github")
        # conventional directory: no provenance, no verification, no relations
        self.assertNotIn("https://", page)
        self.assertNotIn("verification", page.lower())
        self.assertNotIn("relationship", page.lower())

    def test_07_instrumentation_round_trip(self):
        self.post_event(self.app, "/api/events", {
            "participant": "e2e", "task": "T1", "action": "task_start", "target": "T1", "payload": {}})
        self.post_event(self.app, "/api/events", {
            "participant": "e2e", "task": "T1", "action": "complete", "target": "T1",
            "payload": {"outcome": {"correct": True, "discovered": True, "confidence": 0.9}}})
        events = self.get_json("/api/events?task=T1")["events"]
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e["ts"] for e in events))

    def test_08_metrics_computable_from_real_log(self):
        # baseline side of the same session
        self.post_event(self.base, "/events", {
            "participant": "e2e", "task": "T1", "action": "task_start", "target": "T1", "payload": {}})
        self.post_event(self.base, "/events", {
            "participant": "e2e", "task": "T1", "action": "complete", "target": "T1",
            "payload": {"outcome": {"correct": False, "discovered": False, "confidence": 0.2}}})

        events = metrics.load_events(self.event_log)
        report = metrics.aggregate(events, {})
        self.assertEqual(metrics.missing_metrics(report), [])
        self.assertEqual(report["metrics"]["systemvirtue"]["discovery_rate"], 1.0)
        self.assertEqual(report["metrics"]["baseline"]["discovery_rate"], 0.0)

    def test_09_overview_aggregates_match_store(self):
        """Every aggregate on /api/overview must match the store exactly:
        the Ecosystem map view's text alternative is only trustworthy if the
        numbers behind it are."""
        data = self.get_json("/api/overview")
        store = self.app_api.store
        self.assertEqual(data["total_entities"], len(store.entities()))
        self.assertEqual(
            sum(r["count"] for r in data["entity_counts_by_type"]),
            data["total_entities"],
        )
        self.assertEqual(data["total_claims"], len(store.all_claims()))
        self.assertEqual(sum(data["claim_verification"].values()), data["total_claims"])
        self.assertEqual(sum(data["claim_freshness"].values()), data["total_claims"])
        self.assertEqual(data["total_relationships"], len(store.all_relationships()))
        self.assertEqual(
            sum(r["count"] for r in data["relationship_predicates"]),
            data["total_relationships"],
        )
        self.assertEqual(
            sum(data["event_counts_by_type"].values()),
            len(store.ecosystem_events()),
        )

    def test_10_search_total_counts_all_matches(self):
        """`total` is the honest match count even when `results` is capped:
        the UI's "Showing X of Y" must not lie about the corpus."""
        health = self.get_json("/api/health")
        data = self.get_json("/api/search?q=")
        self.assertEqual(data["total"], health["entities"])
        self.assertGreater(data["total"], len(data["results"]))
        none = self.get_json("/api/search?q=zzzznotarealthing")
        self.assertEqual(none["total"], 0)
        self.assertEqual(none["results"], [])


if __name__ == "__main__":
    unittest.main()
