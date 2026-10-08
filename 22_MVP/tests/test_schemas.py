import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from pipeline.ingest import (  # noqa: E402
    AGENT_CONTRACT_SCHEMA,
    CLAIM_SCHEMA,
    ENTITY_SCHEMA,
    EVIDENCE_SCHEMA,
    EVENT_SCHEMA,
    RESEARCH_CONTRACT,
    RELATIONSHIP_SCHEMA,
)
from schemas.validate import SchemaError, assert_valid, validate  # noqa: E402

SEED = json.loads((_ROOT / "corpus" / "seed.json").read_text(encoding="utf-8"))


class TestValidator(unittest.TestCase):
    def test_valid_instance_passes(self):
        self.assertEqual(validate({"a": 1}, {"type": "object", "properties": {"a": {"type": "integer"}}}), [])

    def test_missing_required(self):
        errors = validate({}, {"type": "object", "required": ["a"]})
        self.assertTrue(any("missing required property" in e for e in errors))

    def test_bad_enum(self):
        errors = validate({"state": "nope"}, {"type": "object", "properties": {"state": {"enum": ["ok"]}}})
        self.assertTrue(any("not in enum" in e for e in errors))

    def test_bad_pattern(self):
        errors = validate("xyz", {"type": "string", "pattern": "^abc"})
        self.assertEqual(len(errors), 1)

    def test_unexpected_property(self):
        errors = validate({"a": 1, "b": 2}, {"type": "object", "additionalProperties": False, "properties": {"a": {}}})
        self.assertTrue(any("unexpected property" in e for e in errors))

    def test_nullable_type_list(self):
        self.assertEqual(validate(None, {"type": ["string", "null"]}), [])
        self.assertEqual(validate("x", {"type": ["string", "null"]}), [])

    def test_assert_valid_raises(self):
        with self.assertRaises(SchemaError):
            assert_valid({"a": 1}, {"type": "object", "required": ["b"]})


class TestSeedCorpusSchemas(unittest.TestCase):
    def test_all_evidence_valid(self):
        for ev in SEED["evidence"]:
            assert_valid(ev, EVIDENCE_SCHEMA, ev.get("evidence_id", "?"))

    def test_all_entities_valid(self):
        for ent in SEED["entities"]:
            assert_valid(ent, ENTITY_SCHEMA, ent.get("entity_id", "?"))

    def test_all_claims_valid(self):
        for claim in SEED["claims"]:
            assert_valid(claim, CLAIM_SCHEMA, claim.get("claim_id", "?"))

    def test_all_relationships_valid(self):
        for rel in SEED["relationships"]:
            assert_valid(rel, RELATIONSHIP_SCHEMA, rel.get("relationship_id", "?"))

    def test_all_events_valid(self):
        for event in SEED["events"]:
            assert_valid(event, EVENT_SCHEMA, event.get("event_id", "?"))

    def test_claim_evidence_references_exist(self):
        evidence_ids = {ev["evidence_id"] for ev in SEED["evidence"]}
        for claim in SEED["claims"]:
            self.assertIn(claim["evidence"], evidence_ids, claim["claim_id"])

    def test_relationship_evidence_references_exist(self):
        evidence_ids = {ev["evidence_id"] for ev in SEED["evidence"]}
        for rel in SEED["relationships"]:
            self.assertIn(rel["evidence_id"], evidence_ids, rel["relationship_id"])

    def test_claim_subjects_are_entities(self):
        entity_ids = {ent["entity_id"] for ent in SEED["entities"]}
        for claim in SEED["claims"]:
            self.assertIn(claim["subject"], entity_ids, claim["claim_id"])

    def test_corpus_size(self):
        self.assertGreaterEqual(len(SEED["entities"]), 80)
        self.assertGreaterEqual(len(SEED["claims"]), 80)
        self.assertGreaterEqual(len(SEED["relationships"]), 60)


class TestAgentContract(unittest.TestCase):
    def test_research_contract_valid(self):
        assert_valid(RESEARCH_CONTRACT, AGENT_CONTRACT_SCHEMA, "RESEARCH_CONTRACT")

    def test_contract_covers_spec_section_8(self):
        required = {
            "task_id", "role", "objective", "inputs", "allowed_tools", "allowed_sources",
            "permissions", "risk_class", "deadline", "required_evidence",
            "verification_policy", "output_schema", "fallback", "rollback",
        }
        self.assertEqual(set(AGENT_CONTRACT_SCHEMA["required"]), required)


if __name__ == "__main__":
    unittest.main()
