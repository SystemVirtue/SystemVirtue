# UX Validation Protocol — SystemVirtue MVP

Study-ready protocol for the human evaluation defined in
`16_VALIDATION/UX_VALIDATION.md`. The automated pilot
(`validation/pilot.py`) proves the harness; this protocol is what humans run.

## Design

Within-subjects, counterbalanced comparison of two conditions over the same
knowledge corpus (82 entities, MCP/agents/tools domain):

- **Condition S — SystemVirtue**: search, entity pages with provenance and
  verification state, relationship navigation, comparison, saved state and
  history, optional relationship view, natural-language exploration,
  evidence-backed recommendations.
- **Condition B — Baseline**: conventional keyword search and flat directory
  pages (names + plain descriptions only). Served by
  `validation/baseline/baseline_server.py`.

Counterbalancing: half the participants start with S, half with B
(order recorded per participant). Task order within each condition follows
T1–T10 for comparability; time-on-task is measured per task.

## Participants

Target: 8–12 participants for formative signal, 16+ for quantitative
comparison. Screen for: familiarity with AI tooling, no prior SystemVirtue
exposure. Record AI-tooling experience as a covariate.

## Procedure (per participant, ~60 minutes)

1. Consent (`CONSENT.md`), background questionnaire (experience level).
2. Think-aloud training on a throwaway task.
3. Condition 1: tasks T1–T10 (`TASKS.md`), each ended by the participant
   clicking *Task completed* or *Could not complete* in the task bar.
4. Post-condition instruments: SUS (`SUS.md`), NASA-TLX (`NASA_TLX.md`),
   short interview (`INTERVIEW_GUIDE.md`).
5. Condition 2: same tasks, same instruments.
6. Final interview: forced preference, mental-map probe.

The task selector in the header tags every instrumented event with the active
task. Do not skip the selector: untagged events cannot be scored.

## Measures

See `MEASURES.md`. All metrics are computed by `validation/metrics.py` from
the instrumented event log plus questionnaire responses.

## Analysis plan

- Per metric: condition means, paired comparison (Wilcoxon signed-rank for
  n≥10; descriptive for formative rounds).
- Primary claims require **improved discovery and contextual understanding
  without unacceptable cognitive load** (MVP success criteria 1–3).
- Report errors and failures in full: baseline-favouring results are findings,
  not failures.
- SUS ≥ 68 for condition S is the conventional "above average" reference.

## Ethics and data handling

- Consent before any logging; participant ids are pseudonymous (`p-*`).
- Event logs contain task actions only: no keystrokes, no personal state.
- Personal state (saved entities/history) is in-browser only and is never
  collected.
- Participants may withdraw; their event rows and questionnaire file are
  deleted on request.

## Relationship to the automated pilot

`python3 22_MVP/validation/pilot.py` runs synthetic participants through this
exact protocol to validate instrumentation and metric computation. Synthetic
results must never be reported as human evidence (open question #12).
