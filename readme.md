# SystemVirtue — Current Implementation Status

**Date:** 2026-10-09 · **Scope of this document:** what exists on disk, what is
proven, what is not, and what to do next. Claims marked **[verified]** were
exercised by a test, a live run, or a browser session; claims marked
**[planned]** or **[deferred]** are not.

---

## 1. Precursors

### 1.1 The research package (authoritative specification)

The project began as a research/thesis package, transcribed verbatim into
this repository: **42 Markdown documents** across `00_README/`–`21_APPENDICES/`,
from the manifest file
[ SYSTEMVIRTUE_COMPLETE_RESERACH_THESIS_TECHNICAL_SPECIFICATION_PACKAGE.md](%20SYSTEMVIRTUE_COMPLETE_RESERACH_THESIS_TECHNICAL_SPECIFICATION_PACKAGE.md)
(headings and Markdown preserved exactly as given).

Authority chain ([DOCUMENT_MAP](00_README/DOCUMENT_MAP.md)):
thesis → technical specification → architecture → requirements →
implementation → validation. The documents that govern the build:

- [Master Thesis](01_THESIS/SYSTEMVIRTUE_THESIS.md) and [Strategic Conclusion](01_THESIS/STRATEGIC_CONCLUSION.md)
- [System Requirements](15_TECHNICAL_SPECIFICATION/SYSTEM_REQUIREMENTS.md) — FR-K/S/N/P/R/A/G, claim schema (§5), agent contract (§8), audit record (§10), 10 architectural invariants (§12)
- [UX Validation Framework](16_VALIDATION/UX_VALIDATION.md) — 9 metrics, 10 required test tasks, mandatory baseline comparison
- [MVP Scope](17_ROADMAP/MVP_SCOPE.md) — 12 required features, deliberate exclusions, 6 go/no-go success criteria
- [Requirements Traceability](21_APPENDICES/REQUIREMENTS_TRACEABILITY.md) — evidence→…→validation, 10 named tests
- [Open Research Questions](21_APPENDICES/OPEN_QUESTIONS.md) — 15 questions that must stay open until empirically tested

### 1.2 The notes source

[ENTIRE_INITIAL_CHATGPT_CONVERSATION_THREAD.md](ENTIRE_INITIAL_CHATGPT_CONVERSATION_THREAD.md)
(≈26k lines) is the raw research conversation the package was distilled from.
Its key strategic finding, underweighted in the package itself: free-tier
directories and routers already exist — "a directory of free AI APIs is
absolutely not SystemVirtue." The novel layer is evidence-backed knowledge +
exploration (open question #14: does that layer create value without
execution?).

### 1.3 The approved plan

A review-and-plan phase produced a 4-phase vertical-slice plan (approved
2026-10-09): Phase 0 spec-as-code → Phase 1 knowledge core → Phase 2 MVP
interface → Phase 3 validation kit → Phase 4 go/no-go gate. Stack decided per
[TECHNOLOGY_LANDSCAPE](12_TECHNOLOGY_RESEARCH/TECHNOLOGY_LANDSCAPE.md)
"least complex technology": Python 3.9 stdlib + SQLite + vanilla JS/SVG, zero
external services, zero credentials ([cost controls](13_ZERO_COST/TECHNICAL_COST_CONTROLS.md)).

---

## 2. Current status

Everything below lives in **`22_MVP/`** (56 files). Layout and quickstart:
[22_MVP/README.md](22_MVP/README.md); operating procedure:
[validation/RUNBOOK.md](22_MVP/validation/RUNBOOK.md).

### 2.1 Built and proven **[verified]**

| Component | Where | Status |
| --- | --- | --- |
| JSON Schemas (Claim/Entity/Relationship/Evidence/Event/AgentContract/AuditRecord) + stdlib validator | `22_MVP/schemas/` | Derived verbatim from [SYSTEM_REQUIREMENTS](15_TECHNICAL_SPECIFICATION/SYSTEM_REQUIREMENTS.md) §4–§10 |
| Append-only SQLite store (supersede-chained history, hashed audit rows) + derived search index | `22_MVP/store/` | Indexes rebuildable from canonical knowledge |
| Verification pipeline DISCOVER→…→AUDIT with deterministic acceptance policy | `22_MVP/pipeline/ingest.py` | "Ten copied pages are one source" enforced; hostile input rejected |
| Curated seed corpus | `22_MVP/corpus/` | 82 entities, 93 claims, 80 relationships, 27 excerpt-hashed evidence records, 1 ecosystem event — official sources only, volatile facts excluded |
| Accessible MVP web app (12 required features) | `22_MVP/app/` | Search + facets, entity pages with claim-level provenance/freshness, relationship navigation, comparison, saved/history (browser-only), optional SVG view, constrained NL exploration with citations + uncertainty; semantic-zoom Ecosystem map (macro clusters → meso entities → micro contextual inspector, breadcrumbs, layer toggles, My-Map vs uncharted footprint markers, text-equivalent tables) and Changes & freshness feed; relationship graph with depth selector (1–3) and keyboard zoom — all charts decorative with authoritative table/list equivalents |
| Visualisation technology decision record | `22_MVP/evaluation/VISUALISATION_TECHNOLOGY_EVALUATION.md` | Evidence-based adoption ladder: SVG at current scale → Canvas 2D ≈1k elements → Sigma.js/WebGL ≈5k nodes → WebGPU at million-scale; no dependency needed at 97 entities |
| Baseline comparator (conventional search/directory) | `22_MVP/validation/baseline/` | The B condition UX_VALIDATION requires |
| Metrics engine (9 UX metrics + SUS/NASA-TLX) | `22_MVP/validation/metrics.py` | Known-value unit tests |
| Automated pilot (2 synthetic participants × 2 conditions × 10 tasks) | `22_MVP/validation/pilot.py` | All 14 metric keys computed for both conditions from 154 instrumented events; output labelled synthetic |
| Study-ready protocol pack | `22_MVP/validation/protocol/` | PROTOCOL, TASKS (T1–T10 per condition), CONSENT, SUS, NASA_TLX, MEASURES, INTERVIEW_GUIDE |
| Go/no-go report template wired to the 6 MVP success criteria | `22_MVP/validation/REPORT_TEMPLATE.md` | proceed / pivot / stop decision rule |
| Traceability-as-code: every FR-* → implementation → test, all 10 named validations | `22_MVP/traceability/traceability.json` | Invariants 1–10 each have a machine check |
| **Live MCP Registry sync** | `22_MVP/sync/` | Allowlisted fetch → normalise → read-only diff → pipeline apply; ChangeEvents with `required_tasks`; changed fields become superseding revisions; `--mark-missing` deprecation; `--daemon`/cron scheduling |

### 2.2 Verification evidence **[verified]**

- **Test suite (fresh run 2026-10-09): `cd 22_MVP && python3 -m unittest discover -s tests -t .` → 101 tests, OK, exit 0.** Covers schemas, pipeline policy matrix, error injection, contradiction preservation (FR-K07), append-only history, derived index, all 10 architectural invariants, 100% provenance audit, metrics known values, 10×-corpus scale budget, registry sync (mocked), end-to-end over HTTP, and `/api/overview` aggregates matching the store exactly.
- **Live registry sync runs [verified]:** run 1 fetched 25 real records → 15 unique servers (isLatest dedupe) → 15 creates, 0 errors, every claim carrying registry-URL provenance; immediate re-run → 15 unchanged (idempotent). Daemon loop exercised: 2 scheduled cycles, logs flushed through termination. Store now holds 97 entities (82 curated + 15 live), 16 ecosystem events, 153 audit records.
- **Browser walkthrough [verified]:** keyboard-only operation (skip link → task bar → buttons, 4px visible focus), SVG relationship view absent by default and `aria-hidden` when toggled with the text list as the authoritative alternative (invariant #10), task-tagged instrumentation landing in the event log, NL answers citing claims with stated uncertainty, live-synced entities searchable with verification summaries.

### 2.3 What is intentionally aspirational **[planned]**

The pilot's numbers prove the **measurement apparatus**, not usability.
Synthetic results must never be reported as human evidence (open question
#12). The thesis-level claims — improved discovery, contextual understanding,
trustworthy provenance — remain unproven until a human round runs.

---

## 3. Outstanding

**Blocking the go/no-go gate:**

1. **No human-study data.** The 6 MVP success criteria cannot be evaluated on synthetic output; the study kit is ready in `22_MVP/validation/protocol/` and awaits participants.
2. **Scheduling is not installed** — cron/launchd instructions and `--daemon` exist and work, but no system job runs them (deliberate boundary; your machine, your call).

**Scope boundaries:**

3. **Network allowlist covers only `registry.modelcontextprotocol.io`** ([registry.py](22_MVP/sync/registry.py)); extending it is a deliberate, reviewable edit.
4. **Deferred features** per the plan's exclusion list: semantic search (FR-S02), entitlements/availability/personalisation (FR-P02/P03/P04/R04), execution, payments, marketplace, global completeness.
5. **WCAG 2.2 AA is partially audited** — structural tests + keyboard walkthrough are automated/verified; the full checklist in the RUNBOOK is manual.
6. **Corpus domain scope:** the MCP/agents/tools domain only (curated 2026-10-09 snapshot + live registry records); pricing/quota facts deliberately excluded.
7. **Package citation stubs** ("GitHub+4", "NIST+4", "DOI") remain in the research docs, preserved verbatim per transcription instructions.
8. **Live revision/deprecation paths** are pinned by mocked tests; they fire for real only when registry content changes between runs.

---

## 4. Recommendations (prioritized)

1. **First human study round** — run one real participant through the protocol and fill [REPORT_TEMPLATE.md](22_MVP/validation/REPORT_TEMPLATE.md). This is the only action that can close the gate; everything else is preparation. *(Answers open questions #1–#6.)*
2. **Event-driven work queue** — ChangeEvents already carry `required_tasks`; turn them into queued verification work with outcomes tracked in the audit log. *(Moves the feedback loop in EXECUTIVE_SUMMARY from diagram to mechanism; FR-A.)*
3. **Drift monitoring** — track stale-claim and contradiction rates across sync cycles as an operational signal (freshness dashboard + thresholds). *(FR-A05, self-healing architecture.)*
4. **Extend the registry allowlist** and add scheduled full syncs with `--mark-missing` so deprecation handling runs against reality, not only fixtures.
5. **Resolve the citation stubs** in `20_REFERENCES/` to DOI-level primary sources where the material allows, and record the corrections as claim revisions (history-preserving) rather than edits.
6. **Decision at the gate** — expand, pivot to protocol/API form, or stop, per [STRATEGIC_CONCLUSION.md](01_THESIS/STRATEGIC_CONCLUSION.md); do not scale the corpus before criteria 1–6 have real evidence.

---

*Status claims in §2.1/§2.2 are reproducible via the RUNBOOK commands; §2.3/§3 items are explicitly not verified behavior.*

GRADES spec=8 design=7 correctness=7 quality=6
