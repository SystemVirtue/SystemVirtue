"""Derived search index (CANONICAL_DATA_MODEL.md: indexes are derived).

A simple inverted index over entity names, aliases and accepted description
claims. It can always be rebuilt from the canonical store without losing
epistemic history — that is the point of keeping it derived.
"""

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return _TOKEN_RE.findall(text.lower())


class DerivedIndex:
    def __init__(self):
        self.postings = {}  # token -> {entity_id: weight}

    def _add(self, token, entity_id, weight):
        self.postings.setdefault(token, {})
        self.postings[token][entity_id] = self.postings[token].get(entity_id, 0) + weight

    def index_entity(self, entity):
        eid = entity["entity_id"]
        for token in tokenize(entity["canonical_name"]):
            self._add(token, eid, 3)
        for alias in entity.get("aliases", []):
            for token in tokenize(alias):
                self._add(token, eid, 2)
        for token in tokenize(eid.replace("-", " ").replace("/", " ")):
            self._add(token, eid, 1)

    def index_description(self, entity_id, text):
        for token in tokenize(text):
            self._add(token, entity_id, 1)

    def search(self, query, limit=50):
        scores = {}
        for token in tokenize(query):
            for eid, weight in self.postings.get(token, {}).items():
                scores[eid] = scores.get(eid, 0) + weight
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [eid for eid, _ in ranked[:limit]]

    def documents(self):
        return len({eid for posting in self.postings.values() for eid in posting})


def rebuild(store):
    """Rebuild the derived index from the canonical store."""
    index = DerivedIndex()
    for entity in store.entities():
        index.index_entity(entity)
    for claim in store.all_claims():
        if claim["predicate"] == "DESCRIPTION" and claim["verification_state"] in ("accepted", "conditional"):
            if claim.get("superseded_by") is None:
                index.index_description(claim["subject"], claim["object"])
    return index
