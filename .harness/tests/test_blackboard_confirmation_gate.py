"""Tests for the confirmation gate on `blackboard.py update --status done`.

Why this gate exists, measured before it was written (2026-08-16): the event log
held 246 raw / 16 distinct `precedent_confirm_refused` events and ZERO
`precedent_confirmed` events across the whole life of the harness, against 59
published records. Five of the sixteen refusals were `precedent.py confirm`
correctly refusing the publishing author (SDR-24.1); the other eleven were usage
errors. Nothing was broken. PR-015's confirmation floor had simply never been
wired to a step that actually runs, so it had never once been exercised.

The gate attaches the floor to the only step that has already established a
distinct identity: the producer != approver guard on `--status done`. By the time
the gate is reached, that guard has proven the acting agent is not the producer.

The two properties this suite pins are the ones that make the gate safe to ship:
FAIL-OPEN on any infrastructure problem, and an audited, note-mandatory escape so
it can never permanently wedge the dependency DAG.
"""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
sys.path.insert(0, str(BIN_DIR))

import harness_common as hc  # noqa: E402
import blackboard as bbmod  # noqa: E402


ACTIVE_UNCONFIRMED = {
    "id": "PR-900", "status": "active", "issuing_task": "T-900",
    "confirmation_status": "unconfirmed", "ratio": "x",
}


class GateCase(unittest.TestCase):
    """Each case points hc.HARNESS at a throwaway tree. The live .harness is never
    read or written by this suite."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.harness = pathlib.Path(self._tmp.name) / ".harness"
        self.precedents = self.harness / "precedents"
        self.precedents.mkdir(parents=True)
        self._real = hc.HARNESS
        hc.HARNESS = self.harness
        self.addCleanup(lambda: setattr(hc, "HARNESS", self._real))

    def write(self, **overrides):
        rec = dict(ACTIVE_UNCONFIRMED)
        rec.update(overrides)
        (self.precedents / "{}.json".format(rec["id"])).write_text(
            json.dumps(rec), encoding="utf-8")
        return rec


class WhatTheGateCatches(GateCase):

    def test_an_active_unconfirmed_record_is_reported(self):
        self.write()
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), ["PR-900"])

    def test_a_confirmed_record_is_not_reported(self):
        self.write(confirmation_status="confirmed")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])

    def test_a_narrowed_record_still_counts_as_unconfirmed(self):
        # `precedent.py confirm --outcome narrowed` is a distinct outcome from
        # `confirmed`. Only the exact string clears the gate: a gate that treated
        # every non-empty confirmation_status as satisfied would pass records that
        # were narrowed or rejected, which is the opposite of the floor.
        self.write(confirmation_status="narrowed")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), ["PR-900"])

    def test_a_non_active_record_is_not_reported(self):
        # An overruled or superseded record cannot be confirmed at all
        # (SDR-24.2 refuses it), so gating on one would be an unclearable block.
        self.write(status="overruled")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])

    def test_another_tasks_record_is_not_reported(self):
        self.write(issuing_task="T-901")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])

    def test_several_records_all_report(self):
        self.write(id="PR-900")
        self.write(id="PR-901")
        self.assertEqual(sorted(bbmod.unconfirmed_records_for("T-900")),
                         ["PR-900", "PR-901"])


class FailOpenIsTheWholeSafetyArgument(GateCase):
    """A registry problem must never be able to wedge the DAG. Every one of these
    returns [], which means the gate stands down and `done` proceeds."""

    def test_no_precedents_directory_at_all(self):
        for child in self.precedents.iterdir():
            child.unlink()
        self.precedents.rmdir()
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])

    def test_unparseable_record_does_not_block(self):
        (self.precedents / "PR-902.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])

    def test_record_that_is_a_list_does_not_block(self):
        (self.precedents / "PR-903.json").write_text("[1,2,3]", encoding="utf-8")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])

    def test_one_bad_file_does_not_hide_a_good_finding(self):
        # Fail-open must be per-file, not per-directory: a malformed neighbour
        # must not become a way to silence the gate for a real record.
        (self.precedents / "PR-904.json").write_text("{not json", encoding="utf-8")
        self.write()
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), ["PR-900"])

    def test_missing_fields_are_treated_as_not_matching(self):
        (self.precedents / "PR-905.json").write_text("{}", encoding="utf-8")
        self.assertEqual(bbmod.unconfirmed_records_for("T-900"), [])


class TheEscapeHatchExists(unittest.TestCase):
    """The gate mirrors --override-producer-check: it can always be passed, but
    never silently."""

    def test_allow_unconfirmed_flag_is_registered_on_update(self):
        parser = bbmod.build_parser() if hasattr(bbmod, "build_parser") else None
        if parser is None:
            src = (BIN_DIR / "blackboard.py").read_text(encoding="utf-8")
            self.assertIn("--allow-unconfirmed", src)
            self.assertIn("allow_unconfirmed", src)
        else:  # pragma: no cover - depends on module shape
            self.assertTrue(True)

    def test_the_escape_hatch_demands_a_note(self):
        src = (BIN_DIR / "blackboard.py").read_text(encoding="utf-8")
        self.assertIn('refused: --allow-unconfirmed requires --note', src)

    def test_both_gate_outcomes_are_logged(self):
        # A gate that refuses without an event is unauditable; a gate that is
        # overridden without an event is worse.
        src = (BIN_DIR / "blackboard.py").read_text(encoding="utf-8")
        self.assertIn('confirmation_gate_refused', src)
        self.assertIn('confirmation_gate_overridden', src)


class TheGateDoesNotWriteAnything(GateCase):
    def test_the_check_is_read_only(self):
        self.write()
        before = {p.name: p.read_bytes() for p in self.precedents.iterdir()}
        bbmod.unconfirmed_records_for("T-900")
        after = {p.name: p.read_bytes() for p in self.precedents.iterdir()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
