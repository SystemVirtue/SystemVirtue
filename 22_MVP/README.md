# 22_MVP — SystemVirtue Validation/MVP Vertical Slice

The buildable vertical slice specified by the research package
(`00_README`–`21_APPENDICES` — *not in this repository*, present only in the
local checkout): a provenance-carrying knowledge core for the
AI-agents/MCP ecosystem, an accessible exploration interface, and the
validation kit that can actually run `16_VALIDATION/UX_VALIDATION.md`
(*not in this repository*).

Everything is Python 3.9 stdlib + SQLite + vanilla JS. No dependencies, no
credentials, no paid services.

## Layout

    22_MVP/
    ├── schemas/          JSON Schemas for Claim, Entity, Relationship,
    │                     Evidence, Event, AgentContract, AuditRecord
    │                     (SYSTEM_REQUIREMENTS.md §4–§10) + mini-validator
    ├── corpus/           build_seed.py (hand-curated, official sources)
    │                     → seed.json (deterministic, excerpt-hashed)
    ├── pipeline/         verification pipeline: DISCOVER→EXTRACT→NORMALISE→
    │                     CORROBORATE→CLASSIFY→VERIFY→CONTRADICTIONS→
    │                     FRESHNESS→POLICY→COMMIT→AUDIT (deterministic policy)
    ├── store/            SQLite canonical store (append-only claims with
    │                     history) + derived search index
    ├── app/              MVP web app: JSON API (SYSTEM_REQUIREMENTS §11),
    │                     accessible DOM-first UI, task-tagged instrumentation,
    │                     semantic-zoom Ecosystem map (macro clusters ->
    │                     meso entities -> micro contextual inspector with
    │                     breadcrumbs, layer toggles, footprint markers and
    │                     text-equivalent tables), Changes & freshness view,
    │                     depth/zoom relationship graph
    ├── sync/             live MCP Registry sync: allowlisted fetch →
    │                     normalise → read-only diff → pipeline apply,
    │                     with ChangeEvents, revisions and audit
    ├── validation/       baseline directory (comparator), metrics engine
    │                     (9 UX metrics + SUS/TLX), automated pilot,
    │                     study protocol, report template, runbook
    ├── traceability/     FR-* → implementation → test map + the 10 named
    │                     validations from REQUIREMENTS_TRACEABILITY.md
    ├── tests/            101 tests: schemas, pipeline, store, invariants,
    │                     metrics, scale, registry sync, end-to-end
    └── var/              runtime sqlite db (generated)

## Quickstart

    cd 22_MVP && python3 -m unittest discover -s tests -t .   # all green
    python3 22_MVP/validation/pilot.py                        # harness pilot
    python3 22_MVP/app/server.py                              # UI on :8765

See `validation/RUNBOOK.md` for the full operating procedure.

## How this maps to the research package

- **Knowledge** (thesis §): claims with provenance, uncertainty, freshness,
  contradiction preservation (FR-K01..K07) — `schemas/`, `store/`, `pipeline/`.
- **Experience**: search/browse/entity/relationship/comparison/saved/history/
  explore (FR-S*, FR-N*) — `app/`. Multi-resolution navigation (FR-N03):
  `/api/overview` aggregates → Ecosystem map (type → entity) → entity pages;
  a Changes & freshness view surfaces ChangeEvents and claim
  freshness/verification distribution; the relationship graph has a depth
  selector (1–3) and keyboard zoom. All charts are decorative (`aria-hidden`)
  with authoritative table/list text equivalents (invariant 10); the
  technology rationale is in `evaluation/VISUALISATION_TECHNOLOGY_EVALUATION.md`.
- **Autonomy**: the verification pipeline is deterministic and auditable;
  agent identity lives in contracts, not code (FR-A*, FR-G*) — `pipeline/`.
  Registry sync (FR-A01 discovery, FR-A05 freshness) keeps the corpus
  current without manual re-curation — `sync/`.
- **Governance**: every decision audited with hashes; high-risk never
  auto-accepts; no financial surface exists — invariants 1–10 in
  `tests/test_invariants.py`.
- **Validation**: 10 test tasks, baseline comparator, 9 metrics, protocol —
  `validation/`.

## Deliberately not here (MVP_SCOPE "deliberately excluded")

Execution, payments, credential management, marketplace, global ecosystem
completeness, semantic search (FR-S02), live crawling, LLM-based exploration.
Natural-language exploration is constrained retrieval over verified claims.

## Status honesty

The knowledge corpus is curated from official sources as of 2026-10-09 and
deliberately avoids volatile facts (pricing, quotas). Validation numbers from
`pilot.py` are synthetic harness output — they prove the measurement
apparatus, not usability. Human results come from the protocol in
`validation/protocol/PROTOCOL.md`.
