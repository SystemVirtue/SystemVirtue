# MVP Validation Report — SystemVirtue

Fill after a study round (human) or pilot (harness). Every claim in this
report must cite a metric file, an event log, or an observation.

## 0. Round metadata

- Round: [formative-1 | comparative-1 | pilot-<date>]
- Participants: [n, ids] — or `synthetic (harness only)`
- Corpus: 22_MVP/corpus/seed.json @ [hash]
- Event log: validation/out/[file]
- Report files: validation/out/pilot_report.json (pilot) or analysis output

## 1. Metrics (per condition)

Paste `metrics.to_markdown(report)` output here.

| Metric | systemvirtue | baseline | Δ | Meaningful? |
| --- | --- | --- | --- | --- |

## 2. Go / no-go against MVP success criteria (17_ROADMAP/MVP_SCOPE.md)

| # | Criterion | Evidence | Verdict (pass/fail/partial) |
| --- | --- | --- | --- |
| 1 | Improved discovery | discovery_rate Δ, T2 observations | |
| 2 | Improved contextual understanding | context_retention, T4/T5 | |
| 3 | Acceptable cognitive load | cognitive_load, sus_score | |
| 4 | Trustworthy provenance | T8, why-test, provenance audit | |
| 5 | Useful comparison | comparison_accuracy, T3 | |
| 6 | Repeatable navigation | repeatable_navigation_rate, T6 | |

**Decision rule (MVP_SCOPE):** the project proceeds only if testing
demonstrates all six. Record the decision:

- [ ] PROCEED — expand corpus/domain per 17_ROADMAP/LONG_TERM.md
- [ ] PIVOT — e.g. toward protocol/API form (00_README/EXECUTIVE_SUMMARY.md)
- [ ] STOP — premise not supported (01_THESIS/STRATEGIC_CONCLUSION.md)

## 3. Qualitative findings

- Errors, dead ends, and baseline-favouring observations (report fully).
- Uncertainty/provenance comprehension problems.
- Accessibility findings (WCAG 2.2 AA checklist status).

## 4. Threats to validity

- Synthetic vs human evidence (open question #12).
- Corpus size/domain narrowness (open question #13).
- Order effects despite counterbalancing.

## 5. Next actions

| Action | Owner | Traceable to |
| --- | --- | --- |
