import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "validation"))

import metrics  # noqa: E402


_TS = {"n": 0}


def ev(participant, condition, task, action, target, payload, ts=None):
    if ts is None:
        _TS["n"] += 1
        ts = "2026-10-09T00:%02d:%02dZ" % (_TS["n"] // 60, _TS["n"] % 60)
    return {
        "ts": ts,
        "participant": participant,
        "condition": condition,
        "task": task,
        "action": action,
        "target": target,
        "payload": payload,
    }


class TestSusScoring(unittest.TestCase):
    def test_known_value(self):
        # all 4s -> odd items 3 each (5*3=15), even items 1 each (5*1=5) -> 50
        self.assertEqual(metrics.score_sus([4] * 10), 50.0)

    def test_best_score(self):
        self.assertEqual(metrics.score_sus([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]), 100.0)

    def test_wrong_length_rejected(self):
        with self.assertRaises(ValueError):
            metrics.score_sus([3] * 9)


class TestAggregation(unittest.TestCase):
    def build_events(self):
        events = []
        # systemvirtue: 2 tasks, one discovery, one comparison done right
        events.append(ev("p1", "systemvirtue", "T1", "task_start", "T1", {}, "2026-10-09T00:00:00Z"))
        events.append(ev("p1", "systemvirtue", "T1", "navigate", "a/b",
                         {"predicted": "a/b", "actual": "a/b", "scent_correct": True}, "2026-10-09T00:00:01Z"))
        events.append(ev("p1", "systemvirtue", "T1", "complete", "T1",
                         {"outcome": {"correct": True, "discovered": True, "confidence": 0.8,
                                      "context_retention": 0.9, "recall": 0.8}}, "2026-10-09T00:00:02Z"))
        events.append(ev("p1", "systemvirtue", "T2", "task_start", "T2", {}, "2026-10-09T00:01:00Z"))
        events.append(ev("p1", "systemvirtue", "T2", "compare", "a/b,c/d", {"members": ["a/b", "c/d"]},
                         "2026-10-09T00:01:01Z"))
        events.append(ev("p1", "systemvirtue", "T2", "complete", "T2",
                         {"outcome": {"correct": True, "comparison": True, "confidence": 0.9,
                                      "context_retention": 0.8, "recall": 0.9}}, "2026-10-09T00:01:05Z"))
        # baseline: 2 tasks, errors, failures
        events.append(ev("p1", "baseline", "T1", "task_start", "T1", {}, "2026-10-09T00:02:00Z"))
        events.append(ev("p1", "baseline", "T1", "dead_end", "T1", {"reason": "no feature"}, "2026-10-09T00:02:01Z"))
        events.append(ev("p1", "baseline", "T1", "complete", "T1",
                         {"outcome": {"correct": False, "discovered": False, "confidence": 0.2,
                                      "context_retention": 0.3, "recall": 0.3}}, "2026-10-09T00:02:02Z"))
        events.append(ev("p1", "baseline", "T2", "task_start", "T2", {}, "2026-10-09T00:03:00Z"))
        events.append(ev("p1", "baseline", "T2", "complete", "T2",
                         {"outcome": {"correct": False, "comparison": False, "confidence": 0.1,
                                      "context_retention": 0.2, "recall": 0.2}}, "2026-10-09T00:03:04Z"))
        return events

    def test_known_metric_values(self):
        report = metrics.aggregate(self.build_events(), {})
        sv = report["metrics"]["systemvirtue"]
        bl = report["metrics"]["baseline"]

        self.assertEqual(sv["tasks_attempted"], 2)
        self.assertEqual(sv["tasks_completed"], 2)
        self.assertEqual(sv["discovery_rate"], 0.5)          # 1 of 2 tasks discovered
        self.assertEqual(sv["comparison_accuracy"], 1.0)     # 1 comparison, correct
        self.assertEqual(sv["navigation_errors"], 0)
        self.assertEqual(bl["navigation_errors"], 1)
        self.assertEqual(bl["comparison_accuracy"], 0.0)     # 1 comparison attempt, wrong
        self.assertEqual(sv["information_scent_accuracy"], 1.0)
        self.assertAlmostEqual(sv["recall_score"], 0.85)
        self.assertAlmostEqual(sv["context_retention_score"], 0.85)

    def test_time_on_task(self):
        report = metrics.aggregate(self.build_events(), {})
        self.assertAlmostEqual(report["metrics"]["systemvirtue"]["time_on_task_mean_seconds"], 3.5)

    def test_questionnaires_feed_scores(self):
        sheets = {
            "p1": {
                "sus": {"systemvirtue": [4] * 10, "baseline": [3, 3, 2, 3, 2, 3, 2, 3, 3, 2]},
                "nasa_tlx": {"systemvirtue": [20, 20, 20, 20, 20, 20], "baseline": [60, 60, 60, 60, 60, 60]},
            }
        }
        report = metrics.aggregate(self.build_events(), sheets)
        self.assertEqual(report["metrics"]["systemvirtue"]["sus_score"], 50.0)
        self.assertEqual(report["metrics"]["systemvirtue"]["cognitive_load"], 20.0)
        self.assertEqual(report["metrics"]["baseline"]["cognitive_load"], 60.0)

    def test_all_metrics_present(self):
        report = metrics.aggregate(self.build_events(), {})
        self.assertEqual(metrics.missing_metrics(report), [])

    def test_empty_input_still_reports_keys(self):
        report = metrics.aggregate([], {})
        self.assertEqual(metrics.missing_metrics(report), [])
        self.assertEqual(report["metrics"]["systemvirtue"]["discovery_rate"], 0.0)

    def test_markdown_render(self):
        report = metrics.aggregate(self.build_events(), {})
        md = metrics.to_markdown(report)
        for key in metrics.METRIC_KEYS:
            self.assertIn(key, md)


if __name__ == "__main__":
    unittest.main()
