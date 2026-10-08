"""UX validation metrics engine (UX_VALIDATION.md).

Computes the required metrics from task-tagged instrumented events plus
questionnaire responses:

    discovery rate, time-to-resource, context retention, comparison accuracy,
    recommendation confidence, information scent, cognitive load,
    navigation error, recall

Every metric is computed per condition so the SystemVirtue interface can be
compared against the conventional search/directory baseline.
"""

import json
import statistics
from pathlib import Path

CONDITIONS = ("systemvirtue", "baseline")

METRIC_KEYS = (
    "tasks_attempted",
    "tasks_completed",
    "time_on_task_mean_seconds",
    "discovery_rate",
    "comparison_accuracy",
    "context_retention_score",
    "recall_score",
    "information_scent_accuracy",
    "navigation_errors",
    "repeatable_navigation_rate",
    "recommendation_confidence",
    "calibration_gap",
    "cognitive_load",
    "sus_score",
)


# ------------------------------------------------------------- loading

def load_events(path):
    path = Path(path)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def load_questionnaires(path):
    """Questionnaire file shape:
    {
      "participant-id": {
        "sus": {"systemvirtue": [10 ints 1..5], "baseline": [...]},
        "nasa_tlx": {"systemvirtue": [6 ints 0..100], "baseline": [...]},
        "recall": {"systemvirtue": 0..1, "baseline": 0..1},
        "context_retention": {"systemvirtue": 0..1, "baseline": 0..1}
      }
    }
    """
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------ scoring

def score_sus(responses):
    """Standard SUS scoring: odd items (1-indexed) score response-1,
    even items score 5-response; the sum is scaled to 0..100."""
    if len(responses) != 10:
        raise ValueError("SUS requires exactly 10 responses")
    total = 0
    for i, value in enumerate(responses, start=1):
        total += (value - 1) if i % 2 == 1 else (5 - value)
    return total * 2.5


def score_nasa_tlx(responses):
    if not responses:
        return None
    return statistics.mean(responses)


# ---------------------------------------------------------- aggregation

def _tasks_for(events, condition):
    """Group events by task for one condition into ordered task sessions."""
    sessions = {}
    for ev in events:
        if ev.get("condition") != condition or not ev.get("task"):
            continue
        sessions.setdefault(ev["task"], []).append(ev)
    for task in sessions:
        sessions[task].sort(key=lambda e: e.get("ts") or "")
    return sessions


def _time_on_task(session):
    starts = [e for e in session if e.get("action") == "task_start"]
    ends = [e for e in session if e.get("action") == "complete"]
    if not starts or not ends:
        return None
    from datetime import datetime

    def parse(ts):
        return datetime.fromisoformat(ts.replace("Z", ""))

    return (parse(ends[-1]["ts"]) - parse(starts[0]["ts"])).total_seconds()


def aggregate(events, questionnaires=None):
    questionnaires = questionnaires or {}
    report = {"metrics": {}, "per_condition_details": {}}

    for condition in CONDITIONS:
        sessions = _tasks_for(events, condition)
        condition_events = [e for e in events if e.get("condition") == condition]

        attempted = list(sessions.keys())
        completed_tasks = [
            t for t, s in sessions.items() if any(e.get("action") == "complete" for e in s)
        ]

        durations = [d for d in (_time_on_task(s) for s in sessions.values()) if d is not None]

        completions = [e for e in condition_events if e.get("action") == "complete"]
        outcomes = [e.get("payload", {}).get("outcome", {}) for e in completions]

        discoveries = [o for o in outcomes if o.get("discovered")]
        comparisons = [o for o in outcomes if o.get("comparison") is not None]
        comparison_correct = [o for o in comparisons if o.get("comparison") is True]

        predictions = [
            e.get("payload", {}) for e in condition_events if e.get("action") == "navigate"
        ]
        scent_total = len(predictions)
        scent_correct = len([p for p in predictions if p.get("scent_correct")])

        navigation_errors = len([
            e for e in condition_events if e.get("action") in ("backtrack", "dead_end")
        ])

        restores = [e for e in condition_events if e.get("action") == "restore"]
        restore_ok = len([e for e in restores if e.get("payload", {}).get("restored")])

        confidences = [o.get("confidence") for o in outcomes if o.get("confidence") is not None]
        successes = [o for o in outcomes if o.get("correct") is not None]
        accuracy = (
            len([o for o in successes if o.get("correct")]) / len(successes) if successes else None
        )

        sus_values, tlx_values, recall_values, context_values = [], [], [], []
        for participant, sheet in questionnaires.items():
            if "sus" in sheet and condition in sheet["sus"]:
                sus_values.append(score_sus(sheet["sus"][condition]))
            if "nasa_tlx" in sheet and condition in sheet["nasa_tlx"]:
                v = score_nasa_tlx(sheet["nasa_tlx"][condition])
                if v is not None:
                    tlx_values.append(v)
            if "recall" in sheet and condition in sheet["recall"]:
                recall_values.append(float(sheet["recall"][condition]))
            if "context_retention" in sheet and condition in sheet["context_retention"]:
                context_values.append(float(sheet["context_retention"][condition]))

        # event-derived fallbacks for recall/context when no questionnaire
        for o in outcomes:
            if o.get("recall") is not None:
                recall_values.append(float(o["recall"]))
            if o.get("context_retention") is not None:
                context_values.append(float(o["context_retention"]))

        confidence_mean = statistics.mean(confidences) if confidences else None
        calibration_gap = (
            abs(confidence_mean - accuracy)
            if confidence_mean is not None and accuracy is not None
            else None
        )

        metrics = {
            "tasks_attempted": len(attempted),
            "tasks_completed": len(completed_tasks),
            "time_on_task_mean_seconds": statistics.mean(durations) if durations else None,
            "discovery_rate": (len(discoveries) / len(outcomes)) if outcomes else 0.0,
            "comparison_accuracy": (len(comparison_correct) / len(comparisons)) if comparisons else None,
            "context_retention_score": statistics.mean(context_values) if context_values else None,
            "recall_score": statistics.mean(recall_values) if recall_values else None,
            "information_scent_accuracy": (scent_correct / scent_total) if scent_total else None,
            "navigation_errors": navigation_errors,
            "repeatable_navigation_rate": (restore_ok / len(restores)) if restores else None,
            "recommendation_confidence": confidence_mean,
            "calibration_gap": calibration_gap,
            "cognitive_load": statistics.mean(tlx_values) if tlx_values else None,
            "sus_score": statistics.mean(sus_values) if sus_values else None,
        }
        report["metrics"][condition] = metrics
        report["per_condition_details"][condition] = {
            "tasks": {t: {"events": len(s)} for t, s in sessions.items()},
            "event_count": len(condition_events),
        }

    return report


def missing_metrics(report):
    missing = []
    for condition in CONDITIONS:
        for key in METRIC_KEYS:
            if key not in report["metrics"].get(condition, {}):
                missing.append("%s.%s" % (condition, key))
    return missing


def to_markdown(report):
    lines = ["# Pilot metrics report", ""]
    lines.append("| Metric | systemvirtue | baseline |")
    lines.append("| --- | --- | --- |")
    for key in METRIC_KEYS:
        sv = report["metrics"]["systemvirtue"].get(key)
        bl = report["metrics"]["baseline"].get(key)
        lines.append("| %s | %s | %s |" % (key, _fmt(sv), _fmt(bl)))
    lines.append("")
    lines.append("Harness output: synthetic participants; not evidence about real humans.")
    return "\n".join(lines) + "\n"


def _fmt(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)
