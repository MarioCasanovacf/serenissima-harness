"""Turn accounting in usage_report.py - the input to the k multiplier.

k (how many more turns a cheaper model needs to close the same task) decides
whether a model migration saves anything: input is ~95% cache re-reads, so
total input grows with the SQUARE of the turn count. These tests pin the
aggregation and, more importantly, pin the refusal to compute k from
difficulty-routed historical data.
"""
import importlib.util
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "bin" / "usage_report.py"
spec = importlib.util.spec_from_file_location("usage_report", BIN)
usage_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage_report)


def summary(models):
    return {"models": models}


def test_turns_and_tasks_aggregate_across_runs():
    summaries = [
        summary({"m-a": {"agents": 2, "turns": 10, "raw": 100, "tasks": ["T-001", "T-002"]}}),
        summary({"m-a": {"agents": 1, "turns": 5, "raw": 50, "tasks": ["T-002", "T-003"]}}),
    ]
    row = usage_report.turn_efficiency(summaries)["models"]["m-a"]
    assert row["agents"] == 3
    assert row["turns"] == 15
    # T-002 appears in both runs and must not be double counted
    assert row["tasks_touched"] == 3
    assert row["turns_per_agent"] == 5.0
    assert row["turns_per_task"] == 5.0


def test_shared_tasks_is_the_intersection_not_the_union():
    summaries = [summary({
        "m-a": {"agents": 1, "turns": 4, "raw": 10, "tasks": ["T-001", "T-002"]},
        "m-b": {"agents": 1, "turns": 9, "raw": 10, "tasks": ["T-002", "T-003"]},
    })]
    assert usage_report.turn_efficiency(summaries)["shared_tasks"] == 1


def test_shared_tasks_is_none_with_a_single_model():
    summaries = [summary({"m-a": {"agents": 1, "turns": 4, "raw": 10, "tasks": ["T-001"]}})]
    assert usage_report.turn_efficiency(summaries)["shared_tasks"] is None


def test_never_reports_itself_as_comparable_and_never_emits_k():
    """The confound is structural: this harness routes by difficulty, so two
    models' turns_per_task are not a ratio anyone may divide. The tool must say
    so and must not ship a k field that invites the division."""
    summaries = [summary({
        "cheap": {"agents": 1, "turns": 60, "raw": 10, "tasks": ["T-001"]},
        "frontier": {"agents": 1, "turns": 30, "raw": 10, "tasks": ["T-002"]},
    })]
    report = usage_report.turn_efficiency(summaries)
    assert report["comparable"] is False
    assert "NOT k" in report["note"]
    assert "k" not in report
    for row in report["models"].values():
        assert "k" not in row


def test_zero_tasks_does_not_divide_by_zero():
    summaries = [summary({"m-a": {"agents": 1, "turns": 8, "raw": 10, "tasks": []}})]
    row = usage_report.turn_efficiency(summaries)["models"]["m-a"]
    assert row["turns_per_task"] == 0
    assert row["turns_per_agent"] == 8.0


def test_missing_turns_key_defaults_to_zero():
    """Older summaries predate turn accounting; they must not crash the report."""
    summaries = [summary({"m-a": {"agents": 1, "raw": 10, "tasks": ["T-001"]}})]
    row = usage_report.turn_efficiency(summaries)["models"]["m-a"]
    assert row["turns"] == 0
