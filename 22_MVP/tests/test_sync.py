"""Registry sync tests (network mocked). The live path is exercised by
running `python3 22_MVP/sync/engine.py --limit N` against the real registry;
these tests pin the behaviour deterministically."""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from schemas.validate import assert_valid  # noqa: E402
from store.db import Store  # noqa: E402
from sync import registry  # noqa: E402
from sync.engine import RegistrySync, dedupe_latest, normalize_record, sync_once  # noqa: E402
from pipeline.ingest import CLAIM_SCHEMA, ENTITY_SCHEMA, EVENT_SCHEMA, EVIDENCE_SCHEMA  # noqa: E402


def reg_item(name="io.example/filesync", description="Syncs files.", version="1.0.0",
             status="active", is_latest=True, updated_at="2026-10-01T00:00:00Z",
             published_at="2026-09-01T00:00:00Z"):
    return {
        "server": {
            "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
            "name": name,
            "description": description,
            "title": name.split("/")[-1],
            "version": version,
            "packages": [{"registryType": "npm", "identifier": "filesync-mcp", "version": version}],
            "remotes": [],
        },
        "_meta": {
            "io.modelcontextprotocol.registry/official": {
                "status": status,
                "statusChangedAt": updated_at,
                "publishedAt": published_at,
                "updatedAt": updated_at,
                "isLatest": is_latest,
            }
        },
    }


def make_store():
    store = Store(":memory:")
    # the source entity the AVAILABLE_THROUGH relationship points at
    store.add_evidence({
        "evidence_id": "ev-mcp-registry", "source": "https://registry.modelcontextprotocol.io/",
        "source_type": "registry", "source_root": "registry.modelcontextprotocol.io",
        "title": "Official MCP Registry", "retrieved_at": "2026-10-09",
        "content_hash": "sha256:" + "c" * 64, "derived_from": None, "excerpt": "registry",
    })
    store.add_entity({
        "entity_id": "source/mcp-registry", "entity_type": "source", "canonical_name": "MCP Registry",
        "aliases": [], "source_ids": {}, "evidence_ids": ["ev-mcp-registry"],
        "lifecycle_state": "active", "valid_from": "2026-10-09", "valid_until": None, "history": [],
    })
    return store


class TestNormalization(unittest.TestCase):
    def test_normalized_artifacts_validate_against_schemas(self):
        obs = normalize_record(reg_item())
        engine = RegistrySync(make_store())
        ev = engine.evidence_record(obs)
        ent = engine.entity_record(obs)
        claim = engine.claim_record(obs, "DESCRIPTION", obs["description"], 0.85)
        event = engine.change_event(obs, "capability_change", "medium", "new")
        assert_valid(ev, EVIDENCE_SCHEMA, ev["evidence_id"])
        assert_valid(ent, ENTITY_SCHEMA, ent["entity_id"])
        assert_valid(claim, CLAIM_SCHEMA, claim["claim_id"])
        assert_valid(event, EVENT_SCHEMA, event["event_id"])

    def test_record_without_name_rejected(self):
        with self.assertRaises(ValueError):
            normalize_record({"server": {"description": "anonymous"}})

    def test_latest_only_dedupe(self):
        older = normalize_record(reg_item(version="1.0.0", is_latest=False, updated_at="2026-09-01T00:00:00Z"))
        newer = normalize_record(reg_item(version="1.1.0", is_latest=True, updated_at="2026-10-01T00:00:00Z"))
        kept = dedupe_latest([older, newer])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["version"], "1.1.0")


class TestCreateFlow(unittest.TestCase):
    def test_new_server_committed_with_event_and_audit(self):
        store = make_store()
        report = RegistrySync(store).run([reg_item()])
        self.assertEqual(report["counts"]["create"], 1)

        ent = store.entity("mcp-server/io-example-filesync")
        self.assertIsNotNone(ent)
        claims = store.claims_for("mcp-server/io-example-filesync")
        predicates = {c["predicate"] for c in claims}
        self.assertEqual(predicates, {"REGISTRY_NAME", "DESCRIPTION", "REGISTRY_VERSION", "REGISTRY_STATUS"})

        events = store.ecosystem_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "capability_change")
        self.assertEqual(events[0]["required_tasks"], ["task-sync-verify"])

        self.assertGreaterEqual(len(store.audit_records()), 4)

    def test_malicious_description_rejected_but_record_audited(self):
        store = make_store()
        report = RegistrySync(store).run([reg_item(description='<script>alert(1)</script>')])
        claims = store.claims_for("mcp-server/io-example-filesync")
        predicates = {c["predicate"] for c in claims}
        self.assertNotIn("DESCRIPTION", predicates, "hostile description must not become knowledge")
        self.assertIn("REGISTRY_STATUS", predicates, "clean fields still commit")
        decisions = [r["decision"] for r in store.audit_records()]
        self.assertIn("rejected", decisions)


class TestReviseFlow(unittest.TestCase):
    def test_revision_supersedes_and_preserves_history(self):
        store = make_store()
        RegistrySync(store).run([reg_item()])
        report = RegistrySync(store, now="2026-11-01").run([
            reg_item(description="Syncs files reliably.", version="1.1.0", updated_at="2026-10-28T00:00:00Z")
        ])
        self.assertEqual(report["counts"]["revise"], 1)

        all_claims = store.claims_for("mcp-server/io-example-filesync", include_superseded=True)
        by_id = {c["claim_id"]: c for c in all_claims}
        old_desc = by_id["claim-registry-description-io-example-filesync"]
        self.assertEqual(old_desc["object"], "Syncs files.")
        self.assertIsNotNone(old_desc["superseded_by"])
        self.assertEqual(old_desc["history"][-1]["action"], "superseded")

        current = {c["predicate"]: c for c in store.claims_for("mcp-server/io-example-filesync")}
        self.assertEqual(current["DESCRIPTION"]["object"], "Syncs files reliably.")
        self.assertEqual(current["REGISTRY_VERSION"]["object"], "1.1.0")

        change_events = [e for e in store.ecosystem_events() if e["event_type"] == "capability_change"]
        # one for the create, one per revised field (description + version)
        self.assertEqual(len(change_events), 3)
        self.assertEqual(len({e["event_id"] for e in change_events}), 3)

    def test_idempotent_when_nothing_changed(self):
        store = make_store()
        RegistrySync(store).run([reg_item()])
        claims_before = len(store.all_claims())
        events_before = len(store.ecosystem_events())
        report = RegistrySync(store).run([reg_item()])
        self.assertEqual(report["counts"]["unchanged"], 1)
        self.assertEqual(len(store.all_claims()), claims_before)
        self.assertEqual(len(store.ecosystem_events()), events_before)

    def test_status_deprecation_emits_deprecation_event(self):
        store = make_store()
        RegistrySync(store).run([reg_item()])
        RegistrySync(store, now="2026-12-01").run([reg_item(status="deprecated", updated_at="2026-11-30T00:00:00Z")])
        events = store.ecosystem_events()
        self.assertIn("deprecation", [e["event_type"] for e in events])
        current = {c["predicate"]: c for c in store.claims_for("mcp-server/io-example-filesync")}
        self.assertEqual(current["REGISTRY_STATUS"]["object"], "deprecated")


class TestMissingAndDryRun(unittest.TestCase):
    def test_mark_missing_deprecates_unobserved_entities(self):
        store = make_store()
        RegistrySync(store).run([reg_item()])
        report = RegistrySync(store, now="2027-01-01").run([], mark_missing=True)
        self.assertEqual(report["counts"]["deprecated"], 1)
        ent = store.entity("mcp-server/io-example-filesync")
        self.assertEqual(ent["lifecycle_state"], "deprecated")
        self.assertEqual(ent["history"][-1]["action"], "lifecycle")
        self.assertIn("deprecation", [e["event_type"] for e in store.ecosystem_events()])

    def test_dry_run_writes_nothing(self):
        store = make_store()
        RegistrySync(store).run([reg_item()])
        claims_before = len(store.all_claims())
        report = RegistrySync(store, now="2026-11-01", dry_run=True).run([
            reg_item(description="Changed.", version="2.0.0", updated_at="2026-10-30T00:00:00Z")
        ])
        self.assertEqual(report["counts"]["revise"], 1)
        self.assertEqual(len(store.all_claims()), claims_before)

        report2 = RegistrySync(store, dry_run=True).run([reg_item(name="io.example/new")])
        self.assertEqual(report2["counts"]["create"], 1)
        self.assertIsNone(store.entity("mcp-server/io-example-new"))


class TestNetworkHardControls(unittest.TestCase):
    """TECHNICAL_COST_CONTROLS.md: explicit provider allowlist."""

    def test_allowlist_rejects_unknown_hosts_and_schemes(self):
        with self.assertRaises(registry.AllowlistError):
            registry.check_url("https://evil.example/v0/servers")
        with self.assertRaises(registry.AllowlistError):
            registry.check_url("http://registry.modelcontextprotocol.io/v0/servers")
        registry.check_url("https://registry.modelcontextprotocol.io/v0/servers")

    def test_fetch_failure_leaves_store_untouched(self):
        store = make_store()
        RegistrySync(store).run([reg_item()])
        claims_before = len(store.all_claims())

        def broken_fetcher(**kwargs):
            raise registry.FetchError("registry unreachable: connection refused")

        report = sync_once(store, fetcher=broken_fetcher)
        self.assertEqual(report["status"], "fetch-failed")
        self.assertEqual(len(store.all_claims()), claims_before)

    def test_sync_once_end_to_end_with_mocked_fetch(self):
        store = make_store()

        def fetcher(**kwargs):
            return {"servers": [reg_item()], "metadata": {}}

        report = sync_once(store, fetcher=fetcher, now="2026-10-09")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["create"], 1)


class TestFreshnessTransition(unittest.TestCase):
    def test_claims_age_at_read_time(self):
        from app.server import KnowledgeAPI

        store = make_store()
        store.add_entity({
            "entity_id": "mcp-server/old", "entity_type": "mcp_server", "canonical_name": "Old Server",
            "aliases": [], "source_ids": {}, "evidence_ids": ["ev-mcp-registry"],
            "lifecycle_state": "active", "valid_from": "2024-01-01", "valid_until": None, "history": [],
        })
        store.add_claim({
            "claim_id": "claim-old-desc", "subject": "mcp-server/old", "predicate": "DESCRIPTION",
            "object": "An old description.", "source": "https://registry.modelcontextprotocol.io/",
            "source_type": "registry", "evidence": "ev-mcp-registry",
            "discovered_at": "2024-01-01", "verified_at": "2024-01-01", "valid_from": "2024-01-01",
            "valid_until": None, "agent_id": "test", "model_id": "test", "confidence": 0.9,
            "freshness": "fresh", "verification_state": "accepted", "contradictions": [],
            "policy_state": "auto-accepted", "history": [], "supersedes": None, "superseded_by": None,
        })
        api = KnowledgeAPI(store)
        freshness = api._freshness("mcp-server/old")
        self.assertEqual(freshness["state"], "stale")


if __name__ == "__main__":
    unittest.main()
