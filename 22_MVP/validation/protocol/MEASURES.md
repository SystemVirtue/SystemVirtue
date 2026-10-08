# Measures: metric → instrument

All metrics are computed by `validation/metrics.py` from the instrumented
event log (`validation/out/events.jsonl`) plus `questionnaires.json`.
Metric keys are exactly those in `metrics.METRIC_KEYS`.

| Metric (UX_VALIDATION.md) | Instrument | Field / event source |
| --- | --- | --- |
| Discovery rate | T2 + pre-task inventory | `outcome.discovered` on complete events |
| Time-to-resource | Event timestamps | `task_start` → `complete` per task |
| Context retention | Post-task probe + questionnaire | `outcome.context_retention`, `context_retention` sheet |
| Comparison accuracy | T3 choices | `outcome.comparison` correctness |
| Recommendation confidence | T7 confidence ratings | `outcome.confidence` → `recommendation_confidence`, `calibration_gap` |
| Information scent | Predicted vs actual destination on clicks | navigate events `payload.scent_correct` |
| Cognitive load | NASA-TLX per condition | `nasa_tlx.*` → `cognitive_load` |
| Navigation error | Instrumented actions | count of `backtrack` + `dead_end` events |
| Recall | End-of-session structure probe | `outcome.recall`, `recall` sheet |
| (Usability reference) | SUS per condition | `sus.*` → `sus_score` |
| (Repeat navigation) | T6 restore actions | `restore` events → `repeatable_navigation_rate` |

## Event vocabulary (what the UI emits)

| action | meaning | payload |
| --- | --- | --- |
| `task_start` | task selector changed | — |
| `search` | query submitted | `q`, `type`, mode flags |
| `navigate` | entity opened | `predicted`, `actual`, `scent_correct` |
| `backtrack` | re-opened a previously visited entity | — |
| `compare` | comparison constructed | `members` |
| `save` | personal save toggled | `saved` |
| `restore` | returned to earlier state | `restored` |
| `dead_end` | feature unavailable / no path (baseline) | `reason` |
| `view_graph` | optional visualisation opened | — |
| `complete` | task finished | `outcome{correct, discovered, comparison, confidence, context_retention, recall}` |

## Scoring notes

- Discovery rate denominator = tasks with a complete event.
- Comparison accuracy denominator = tasks that attempted a comparison
  (baseline attempts count; failing for lack of feature is a finding).
- Missing questionnaires yield `n/a`, never 0.
