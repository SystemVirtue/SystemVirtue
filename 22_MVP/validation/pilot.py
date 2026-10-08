"""Automated pilot: synthetic participants run the ten required test tasks
from UX_VALIDATION.md against BOTH conditions through the real instrumented
stack (app server + baseline directory, shared event log).

Purpose: prove the validation harness end to end — every metric computable,
both conditions comparable. This is explicitly a HARNESS TEST, not evidence
about human usability; open question #12 (can synthetic users predict real
usability?) stays open. Human participants run the same protocol in
validation/protocol/PROTOCOL.md.

Usage:  python3 22_MVP/validation/pilot.py
"""

import json
import os
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUT = _ROOT / "validation" / "out"
EVENT_LOG_PATH = OUT / "pilot_events.jsonl"
QUESTIONNAIRE_PATH = OUT / "questionnaires.json"


def _get_json(base, path):
    with urlopen(base + path, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def make_emitter(base, api_prefix, participant, condition, task_ref):
    """Emit instrumented events exactly as each UI does (POST endpoint)."""

    def emit(action, target, payload):
        event = {
            "participant": participant,
            "task": task_ref["task"],
            "action": action,
            "target": target,
            "payload": payload,
        }
        if condition == "baseline":
            event["condition"] = "baseline"
        req = Request(
            base + api_prefix,
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            resp.read()

    return emit


# ------------------------------------------------------------- task runs
# Each runner: (emit, base, api, get) + outcome dicts recording what the
# participant achieved. Baseline capabilities are deliberately narrower:
# that difference is what the study measures.

def t1_find(emit, base, get, api_prefix):
    emit("task_start", "T1", {})
    data = get("/api/search?q=web%20search") if api_prefix == "/api/events" else get("/search?q=web%20search")
    emit("search", "web search", {"q": "web search"})
    emit("navigate", "capability/web-search", {"predicted": "capability/web-search", "actual": "capability/web-search", "scent_correct": True})
    emit("complete", "T1", {"outcome": {"correct": True, "discovered": False, "confidence": 0.9,
                                        "context_retention": 0.9, "recall": 0.85}})
    return data


def t2_discover(emit, base, get, api_prefix):
    emit("task_start", "T2", {})
    get("/api/search?q=structured%20memory" if api_prefix == "/api/events" else "/search?q=memory")
    emit("search", "structured memory", {"q": "structured memory"})
    emit("navigate", "mcp-server/memory", {"predicted": "mcp-server/memory", "actual": "mcp-server/memory", "scent_correct": True})
    emit("complete", "T2", {"outcome": {"correct": True, "discovered": True, "confidence": 0.8,
                                        "context_retention": 0.85, "recall": 0.8}})
    return True


def t3_compare(emit, base, get, api_prefix):
    emit("task_start", "T3", {})
    if api_prefix == "/api/events":
        get("/api/compare?ids=mcp-server/brave-search,mcp-server/fetch")
        emit("compare", "mcp-server/brave-search,mcp-server/fetch", {"members": ["mcp-server/brave-search", "mcp-server/fetch"]})
        emit("complete", "T3", {"outcome": {"correct": True, "comparison": True, "confidence": 0.85,
                                            "context_retention": 0.85, "recall": 0.8}})
    else:
        emit("search", "brave", {"q": "brave"})
        emit("dead_end", "T3", {"reason": "no comparison support in directory"})
        emit("complete", "T3", {"outcome": {"correct": False, "comparison": False, "confidence": 0.3,
                                            "context_retention": 0.3, "recall": 0.3}})
    return True


def t4_relationship(emit, base, get, api_prefix):
    emit("task_start", "T4", {})
    if api_prefix == "/api/events":
        data = get("/api/graph?center=mcp-server/github&depth=1")
        assert data["edges"], "graph must expose edges"
        emit("navigate", "mcp-server/github", {"predicted": "tool/search-code", "actual": "tool/search-code", "scent_correct": True})
        emit("complete", "T4", {"outcome": {"correct": True, "confidence": 0.85,
                                            "context_retention": 0.9, "recall": 0.85}})
    else:
        get("/entity/mcp-server/github")
        emit("dead_end", "T4", {"reason": "no relationship data in directory"})
        emit("complete", "T4", {"outcome": {"correct": False, "confidence": 0.2,
                                            "context_retention": 0.25, "recall": 0.25}})
    return True


def t5_availability(emit, base, get, api_prefix):
    emit("task_start", "T5", {})
    if api_prefix == "/api/events":
        data = get("/api/entity/model/claude-family")
        assert data["relationships"], "availability must be derivable from relationships"
        emit("navigate", "model/claude-family", {"predicted": "provider/anthropic-api", "actual": "provider/anthropic-api", "scent_correct": True})
        emit("complete", "T5", {"outcome": {"correct": True, "confidence": 0.8,
                                            "context_retention": 0.85, "recall": 0.8}})
    else:
        get("/entity/model/claude-family")
        emit("dead_end", "T5", {"reason": "description has no availability information"})
        emit("complete", "T5", {"outcome": {"correct": False, "confidence": 0.2,
                                            "context_retention": 0.2, "recall": 0.2}})
    return True


def t6_return(emit, base, get, api_prefix):
    emit("task_start", "T6", {})
    if api_prefix == "/api/events":
        emit("restore", "mcp-server/memory", {"restored": True})
        emit("complete", "T6", {"outcome": {"correct": True, "confidence": 0.9,
                                            "context_retention": 0.95, "recall": 0.9}})
    else:
        emit("dead_end", "T6", {"reason": "no saved state or history in directory"})
        emit("complete", "T6", {"outcome": {"correct": False, "confidence": 0.1,
                                            "context_retention": 0.15, "recall": 0.15}})
    return True


def t7_recommendation(emit, base, get, api_prefix):
    emit("task_start", "T7", {})
    if api_prefix == "/api/events":
        data = get("/api/recommend?task=task/web-research")
        assert data["ranking"] and data["uncertainty"], "recommendation must expose reasons and uncertainty"
        emit("search", "recommendation", {"q": "task/web-research"})
        emit("complete", "T7", {"outcome": {"correct": True, "confidence": 0.8,
                                            "context_retention": 0.85, "recall": 0.8}})
    else:
        emit("search", "recommendation", {"q": "recommendation"})
        emit("dead_end", "T7", {"reason": "no recommendations in directory"})
        emit("complete", "T7", {"outcome": {"correct": False, "confidence": 0.15,
                                            "context_retention": 0.2, "recall": 0.2}})
    return True


def t8_uncertainty(emit, base, get, api_prefix):
    emit("task_start", "T8", {})
    if api_prefix == "/api/events":
        data = get("/api/entity/mcp-server/google-drive")
        states = [c["claim"]["verification_state"] for c in data["claims"]]
        assert states, "entity page must expose verification state"
        emit("navigate", "mcp-server/google-drive", {"predicted": "conditional evidence", "actual": "conditional evidence", "scent_correct": True})
        emit("complete", "T8", {"outcome": {"correct": True, "confidence": 0.75,
                                            "context_retention": 0.85, "recall": 0.8}})
    else:
        get("/entity/mcp-server/google-drive")
        emit("dead_end", "T8", {"reason": "no verification state in directory"})
        emit("complete", "T8", {"outcome": {"correct": False, "confidence": 0.1,
                                            "context_retention": 0.15, "recall": 0.15}})
    return True


def t9_no_visualisation(emit, base, get, api_prefix):
    emit("task_start", "T9", {})
    get("/api/search?q=filesystem" if api_prefix == "/api/events" else "/search?q=filesystem")
    emit("search", "filesystem", {"q": "filesystem", "graph": "off"})
    emit("navigate", "mcp-server/filesystem", {"predicted": "mcp-server/filesystem", "actual": "mcp-server/filesystem", "scent_correct": True})
    emit("complete", "T9", {"outcome": {"correct": True, "confidence": 0.85,
                                        "context_retention": 0.85, "recall": 0.8}})
    return True


def t10_accessibility(emit, base, get, api_prefix):
    emit("task_start", "T10", {})
    get("/api/search?q=issue" if api_prefix == "/api/events" else "/search?q=issue")
    emit("search", "issue", {"q": "issue", "input_mode": "keyboard"})
    emit("navigate", "capability/issue-tracking", {"predicted": "capability/issue-tracking", "actual": "capability/issue-tracking", "scent_correct": True})
    emit("complete", "T10", {"outcome": {"correct": True, "confidence": 0.8,
                                         "context_retention": 0.85, "recall": 0.8}})
    return True


TASKS = [t1_find, t2_discover, t3_compare, t4_relationship, t5_availability,
         t6_return, t7_recommendation, t8_uncertainty, t9_no_visualisation, t10_accessibility]

SYNTHETIC_QUESTIONNAIRES = {
    "_meta": {
        "synthetic": True,
        "note": "Synthetic responses generated by the harness. Human studies replace this file.",
    },
    "synthetic-01": {
        "sus": {"systemvirtue": [4, 4, 5, 4, 4, 4, 5, 4, 4, 4], "baseline": [3, 3, 2, 3, 2, 3, 2, 3, 3, 2]},
        "nasa_tlx": {"systemvirtue": [20, 25, 30, 20, 25, 15], "baseline": [55, 60, 50, 65, 60, 50]},
        "recall": {"systemvirtue": 0.9, "baseline": 0.5},
        "context_retention": {"systemvirtue": 0.9, "baseline": 0.4},
    },
    "synthetic-02": {
        "sus": {"systemvirtue": [4, 5, 4, 4, 5, 4, 4, 4, 5, 4], "baseline": [2, 3, 3, 2, 3, 2, 3, 2, 3, 3]},
        "nasa_tlx": {"systemvirtue": [25, 20, 25, 30, 20, 20], "baseline": [60, 55, 65, 60, 55, 60]},
        "recall": {"systemvirtue": 0.85, "baseline": 0.45},
        "context_retention": {"systemvirtue": 0.85, "baseline": 0.35},
    },
}


def run_pilot():
    import importlib

    os.environ["SV_EVENT_LOG"] = str(EVENT_LOG_PATH)
    os.environ["SV_DB"] = ":memory:"
    if EVENT_LOG_PATH.exists():
        EVENT_LOG_PATH.unlink()

    app_server = importlib.import_module("app.server")
    baseline_server = importlib.import_module("validation.baseline.baseline_server")

    app_srv, _ = app_server.create_server(port=0, db_path=":memory:")
    base_srv, _ = baseline_server.create_server(port=0, db_path=":memory:")
    app_base = "http://127.0.0.1:%d" % app_srv.server_address[1]
    base_base = "http://127.0.0.1:%d" % base_srv.server_address[1]

    threads = [
        threading.Thread(target=app_srv.serve_forever, daemon=True),
        threading.Thread(target=base_srv.serve_forever, daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        # counterbalanced: synthetic-01 starts with systemvirtue,
        # synthetic-02 starts with baseline
        runs = [
            ("synthetic-01", app_base, "/api/events", "/api/events", "systemvirtue"),
            ("synthetic-01", base_base, "/events", "/events", "baseline"),
            ("synthetic-02", base_base, "/events", "/events", "baseline"),
            ("synthetic-02", app_base, "/api/events", "/api/events", "systemvirtue"),
        ]

        def get_factory(base, api_prefix):
            def get(path):
                if api_prefix == "/api/events":
                    return _get_json(base, path)
                # baseline serves plain HTML; reachability is enough
                with urlopen(base + path, timeout=10) as resp:
                    body = resp.read()
                assert body, "baseline page must not be empty"
                return {"ok": True}
            return get

        for participant, base, api_prefix, _, condition in runs:
            get = get_factory(base, api_prefix)
            for task_fn in TASKS:
                task_ref = {"task": "T%s" % task_fn.__name__.split("_")[0][1:]}
                emit = make_emitter(base, api_prefix, participant, condition, task_ref)
                task_fn(emit, base, get, api_prefix)
    finally:
        app_srv.shutdown()
        base_srv.shutdown()

    # questionnaires + metrics
    OUT.mkdir(parents=True, exist_ok=True)
    QUESTIONNAIRE_PATH.write_text(json.dumps(SYNTHETIC_QUESTIONNAIRES, indent=2) + "\n", encoding="utf-8")

    sys.path.insert(0, str(_ROOT / "validation"))
    import metrics

    events = metrics.load_events(EVENT_LOG_PATH)
    questionnaires = metrics.load_questionnaires(QUESTIONNAIRE_PATH)
    report = metrics.aggregate(events, questionnaires)

    missing = metrics.missing_metrics(report)
    (OUT / "pilot_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (OUT / "pilot_report.md").write_text(metrics.to_markdown(report), encoding="utf-8")

    print(metrics.to_markdown(report))
    print("events recorded:", len(events))
    if missing:
        raise SystemExit("MISSING METRICS: %s" % missing)
    print("PILOT OK: all %d metrics computed for both conditions." % len(metrics.METRIC_KEYS))


if __name__ == "__main__":
    run_pilot()
