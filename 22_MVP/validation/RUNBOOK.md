# Runbook — SystemVirtue MVP

Everything runs on Python 3.9 stdlib. No network access is required after
curation; no credentials; no paid services (zero-cost hard controls).

## 1. Build / rebuild the seed corpus

    python3 22_MVP/corpus/build_seed.py

Deterministic: writes `22_MVP/corpus/seed.json` (~82 entities, ~93 claims,
80 relationships, 27 evidence records). Evidence `content_hash` values are
SHA-256 of the curated excerpts.

## 2. Ingest into the canonical store

    python3 -c "import sys; sys.path.insert(0,'22_MVP'); from app.server import open_store; s=open_store(); print(len(s.all_claims()), 'claims')"

First run creates `22_MVP/var/systemvirtue.db` and runs the full
verification pipeline (DISCOVER→…→AUDIT). Delete the db to re-ingest.

## 3. Test suite (81 tests)

    cd 22_MVP && python3 -m unittest discover -s tests -t .

Covers: schemas, pipeline policy matrix, error injection, contradiction
preservation, append-only history, derived index, the 10 architectural
invariants, provenance audit, metrics, scale, and end-to-end over HTTP.
All must pass before any validation round.

## 4. Automated pilot (harness validation)

    python3 22_MVP/validation/pilot.py

Runs 2 synthetic participants × 2 conditions × 10 tasks through the real
servers and writes:

- `validation/out/pilot_events.jsonl` — instrumented events
- `validation/out/questionnaires.json` — synthetic responses (labelled)
- `validation/out/pilot_report.json` / `pilot_report.md` — all 14 metrics

Exit 0 = every metric computable for both conditions. **Never report pilot
numbers as human results.**

## 5. Registry sync (live corpus maintenance)

    python3 22_MVP/sync/engine.py --limit 25            # one sync cycle
    python3 22_MVP/sync/engine.py --dry-run --limit 25  # report only, no writes
    python3 22_MVP/sync/engine.py --daemon --interval 86400   # persistent loop

Scheduling without a daemon (cron):

    0 4 * * * cd /path/to/SystemVirtue_Concept && python3 22_MVP/sync/engine.py --limit 200

Semantics:

- Fetch failures leave the knowledge base untouched (NFR availability).
- New registry entries become entities+claims through the verification
  pipeline; changed descriptions/versions/status become **superseding
  revisions** (history preserved); every change emits a ChangeEvent with
  `required_tasks` and an audit row.
- `--mark-missing` additionally deprecates previously-synced servers that
  are no longer in the registry (use on full, unfiltered syncs only).
- Network hard controls: HTTPS + host allowlist in `sync/registry.py`,
  timeout and response size caps, no credentials.
- Latest run summary: `22_MVP/var/sync_report.json`.

## 6. Serve the interfaces (human study / manual checks)

    python3 22_MVP/app/server.py                      # SystemVirtue, port 8765
    python3 22_MVP/validation/baseline/baseline_server.py  # baseline, port 8766

Env: `SV_PORT`, `SV_BASELINE_PORT`, `SV_DB`, `SV_EVENT_LOG`.

## 7. Manual browser checklist (per UI release)

Keyboard-only pass (WCAG 2.2 AA):

- [ ] Tab reaches every control in logical order; focus ring always visible
- [ ] Skip link works; view changes move focus to the heading
- [ ] Search → entity → relationship navigation completable without a mouse
- [ ] All actions operable with Enter/Space; no hover-only affordances
- [ ] Text zoom 200% without loss of content
- [ ] Screen reader announces result regions (aria-live) after searches

Visualisation-independence pass (invariant #10):

- [ ] Complete T1–T5 with the relationship view OFF (default)
- [ ] Relationship list alone answers T4 ("how does X relate to Y")
- [ ] Opening the optional graph adds nothing required for any task

Instrumentation pass:

- [ ] Select task in the task bar before tasks; verify events land in the log
      (`curl localhost:8765/api/events?task=T1`)
- [ ] Compare against baseline events (condition field differs)

## 8. Human study round

1. Run the checklist; run the tests; run the pilot.
2. Follow `protocol/PROTOCOL.md` with `protocol/TASKS.md`.
3. Record questionnaires per `protocol/SUS.md` / `protocol/NASA_TLX.md`
   in `validation/out/questionnaires.json`.
4. Compute metrics (`python3 -c "import sys; sys.path.insert(0,'22_MVP/validation'); import metrics; ..."`) or extend `pilot.py`'s aggregation block.
5. Fill `REPORT_TEMPLATE.md`, including the go/no-go decision.

## 9. Failure modes and rollback

- Knowledge corruption: claims are append-only; supersede with a corrected
  revision (FR-G05). Nothing overwrites history.
- Ingest failure: the existing validated knowledge base is untouched
  (NFR availability); fix the input and re-run.
- Cost: structurally impossible — there is no financial surface (invariant 8).
