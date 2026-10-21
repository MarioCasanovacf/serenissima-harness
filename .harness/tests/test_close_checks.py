"""T-458 / option 6b: IMP-6 (an act with no act_signed event is anomalous) and the
one-command epic-close report that wraps attest.py forks, warrant.py reconcile and
IMP-6 together.

Ratified 2026-10-21 (.harness/operator-rulings-2026-10-21.md, decision 1, option 6b) and
coordinator-decisions-ruling-round-2.md D-22 (IMP-1..IMP-6) / IMP-7 ("nothing above
attaches a consequence").

WHY close_checks.py'S WRAPPING OF attest.py/warrant.py IS PINNED AGAINST STUBS, NOT
ONLY THE REAL TOOLS. Both modules are under concurrent edit elsewhere in this epic
(T-448 and siblings). The IMP-7 claim this suite most needs to protect -- that a
sub-tool's own exit code (warrant.py `reconcile` exits 3 on orphans, attest.py can exit
2 on a refusal) never becomes THIS tool's exit code -- is pinned against two tiny stub
scripts that print a fixed JSON body and exit with a fixed code, so the pin holds
regardless of whichever half-finished state either real tool is in on a given day. A
separate class below (`RealClis`) also exercises the actual attest.py and warrant.py
CLIs against a throwaway root, and against the live `.harness/` tree, for integration
confidence -- but no assertion in this file depends on EITHER real tool returning a
particular exit code.
"""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
sys.path.insert(0, str(BIN_DIR))
import close_checks as cc  # noqa: E402
import event_stats  # noqa: E402


def _write_act(root, name, seq, kind="commit", task="T-1", prev="GENESIS"):
    d = pathlib.Path(root) / "acts" / name
    d.mkdir(parents=True, exist_ok=True)
    act = {"schema_version": 1, "name": name, "seq": seq, "kind": kind, "ref": "",
           "body": {}, "prev": prev, "ts": "2026-10-21T00:00:00Z",
           "namespace": "harness-act", "task": task, "intent": ""}
    (d / f"{seq:03d}.json").write_text(json.dumps(act), encoding="utf-8")
    return act


def _write_event(root, **fields):
    rec = {"ts": "2026-10-21T00:00:01Z", "event": "act_signed", "agent": "tester"}
    rec.update(fields)
    path = pathlib.Path(root) / "logs" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


class Imp6Check(unittest.TestCase):
    """The core comparison: acts on disk vs act_signed events, deduped per D-9."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "h"
        self.root.mkdir()

    def test_an_act_with_a_matching_event_is_not_anomalous(self):
        _write_act(self.root, "aurelia", 1)
        _write_event(self.root, name="aurelia", seq=1, act_kind="commit", task="T-1")
        out = cc.imp6_check(self.root)
        self.assertEqual(out["acts_total"], 1)
        self.assertEqual(out["acts_matched"], 1)
        self.assertEqual(out["acts_anomalous"], [])

    def test_an_act_with_no_matching_event_is_anomalous(self):
        _write_act(self.root, "orso", 1)
        out = cc.imp6_check(self.root)
        self.assertEqual(out["acts_total"], 1)
        self.assertEqual(out["acts_matched"], 0)
        self.assertEqual(len(out["acts_anomalous"]), 1)
        self.assertEqual(out["acts_anomalous"][0]["name"], "orso")
        self.assertEqual(out["acts_anomalous"][0]["seq"], 1)

    def test_a_different_seq_does_not_accidentally_match(self):
        _write_act(self.root, "orso", 2)
        _write_event(self.root, name="orso", seq=1, act_kind="commit", task="T-1")
        out = cc.imp6_check(self.root)
        self.assertEqual(len(out["acts_anomalous"]), 1)
        self.assertEqual(out["acts_anomalous"][0]["seq"], 2)

    def test_replayed_events_collapse_to_one_distinct_but_raw_stays_high(self):
        """D-9: two events are the SAME when they agree on every field except `ts`.
        A burst of three act_signed events that differ ONLY in `ts` must still count
        as raw=3, distinct=1 -- and must still match the one act on disk.

        `ts` is varied EXPLICITLY across the three writes (not left at
        `_write_event`'s fixed default). A dedup key that wrongly includes `ts` in its
        identity (e.g. a reimplementation keyed on `(ts, name)` instead of calling
        event_stats.identity) would see three distinct identities here and report
        distinct=3; against a fixture with a constant default `ts`, that regression
        would be invisible, because all three events would already share one `ts` for
        the wrong reason. Varying `ts` for real is what makes this test actually pin
        the D-9 predicate rather than passing by coincidence."""
        _write_act(self.root, "aurelia", 1)
        for ts in ("2026-10-21T00:00:01Z", "2026-10-21T00:00:02Z",
                   "2026-10-21T00:00:03Z"):
            _write_event(self.root, name="aurelia", seq=1, act_kind="commit",
                         task="T-1", ts=ts)
        out = cc.imp6_check(self.root)
        ec = out["act_signed_events"]
        self.assertEqual(ec["raw"], 3)
        self.assertEqual(ec["distinct"], 1)
        self.assertEqual(out["acts_matched"], 1)
        self.assertEqual(out["acts_anomalous"], [])

    def test_a_dedup_keyed_on_ts_instead_of_identity_would_be_caught_here(self):
        """A second, deliberately independent pin on the same mutant class as above:
        five act_signed events for ONE act, each with a distinct `ts`, must still
        collapse to distinct=1. This does not depend on the three-event fixture above
        and exercises a different count (5, not 3), so a fix that special-cases 3
        duplicates would not satisfy it either."""
        _write_act(self.root, "orso", 7)
        for i in range(5):
            _write_event(self.root, name="orso", seq=7, act_kind="commit", task="T-9",
                         ts=f"2026-10-21T00:00:{i:02d}Z")
        out = cc.imp6_check(self.root)
        ec = out["act_signed_events"]
        self.assertEqual(ec["raw"], 5)
        self.assertEqual(ec["distinct"], 1)
        self.assertEqual(out["acts_anomalous"], [])

    def test_two_properly_signed_acts_by_the_same_name_with_different_seq_both_match(
            self):
        """Pins the dedup key from the COARSE side (round 3): a key that drops `seq`
        (e.g. a reimplementation keyed on `name` alone) would wrongly treat two
        DIFFERENT acts by one agent as duplicates of each other. The ordinary case --
        one agent, two acts, seq 7 and seq 8, each with its own real act_signed event
        -- must come back as raw=2, distinct=2, both matched, and NEITHER reported
        anomalous. A dedup keyed on name only collapses the seq=7 identity and the
        seq=8 identity into one `seen` entry, drops the seq=8 event out of the
        distinct set, and the properly-signed act #8 is then reported ANOMALOUS even
        though its event is on disk -- a false positive on the single most ordinary
        scenario this module has to handle."""
        _write_act(self.root, "orso", 7)
        _write_act(self.root, "orso", 8)
        _write_event(self.root, name="orso", seq=7, act_kind="commit", task="T-1")
        _write_event(self.root, name="orso", seq=8, act_kind="commit", task="T-1")
        out = cc.imp6_check(self.root)
        ec = out["act_signed_events"]
        self.assertEqual(ec["raw"], 2)
        self.assertEqual(ec["distinct"], 2)
        self.assertEqual(out["acts_total"], 2)
        self.assertEqual(out["acts_matched"], 2)
        self.assertEqual(out["acts_anomalous"], [])

    def test_events_sharing_name_and_seq_but_differing_in_another_d9_field_stay_distinct(
            self):
        """The same coarsening failure mode, generalized beyond `seq`: D-9's own
        text defines identity as every field except `ts`, not `(name, seq)` and not
        `(name, seq, act_kind)`. Two act_signed events that share BOTH `name` and
        `seq` but disagree on `task` are still two distinct events under D-9 (they
        are not replays of each other -- a replay is byte-identical but for `ts`), so
        this must report raw=2, distinct=2. A dedup key narrowed to `(name, seq)` --
        or to `(name, seq, act_kind)` while still varying `task` -- would wrongly
        collapse this to distinct=1, understating raw replay the way
        TELEMETRY-PROVENANCE-A (M-1) exists to catch in the other direction."""
        _write_act(self.root, "aurelia", 1)
        _write_event(self.root, name="aurelia", seq=1, act_kind="commit", task="T-1")
        _write_event(self.root, name="aurelia", seq=1, act_kind="commit", task="T-2")
        out = cc.imp6_check(self.root)
        ec = out["act_signed_events"]
        self.assertEqual(ec["raw"], 2)
        self.assertEqual(ec["distinct"], 2)
        # matching is still keyed on (name, seq) only, so the one act on disk still
        # matches -- this test is about the raw/distinct count, not the match set.
        self.assertEqual(out["acts_matched"], 1)
        self.assertEqual(out["acts_anomalous"], [])

    def test_the_dedup_predicate_is_imported_from_event_stats_not_reimplemented(self):
        """Pins the no-drift claim directly: close_checks.py must use event_stats'
        own identity() object, not a lookalike copy of it."""
        self.assertIs(cc.event_stats.identity, event_stats.identity)
        self.assertEqual(cc.event_stats.DEDUP_RULE, event_stats.DEDUP_RULE)

    def test_unparseable_act_and_event_lines_are_counted_not_dropped_and_not_crashed(self):
        d = pathlib.Path(self.root) / "acts" / "orso"
        d.mkdir(parents=True)
        (d / "001.json").write_text("{not json", encoding="utf-8")
        events = pathlib.Path(self.root) / "logs" / "events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        events.write_text("not json either\n", encoding="utf-8")
        out = cc.imp6_check(self.root)
        self.assertEqual(out["acts_unparseable"], 1)
        self.assertEqual(out["acts_total"], 0)
        self.assertEqual(out["act_signed_events"]["lines_unparseable"], 1)

    def test_only_act_signed_events_are_counted_not_every_event_kind(self):
        _write_act(self.root, "orso", 1)
        _write_event(self.root, name="orso", seq=1, act_kind="commit", task="T-1",
                     event="some_other_event")
        out = cc.imp6_check(self.root)
        self.assertEqual(out["act_signed_events"]["raw"], 0)
        self.assertEqual(len(out["acts_anomalous"]), 1)

    def test_the_report_carries_no_verdict_field(self):
        """IMP-7: computed and reported only. A pass/fail/verdict field here would be
        this tool deciding what an anomaly means, which D-22/IMP-7 forbids."""
        _write_act(self.root, "orso", 1)
        out = cc.imp6_check(self.root)
        forbidden = {"ok", "pass", "passed", "fail", "failed", "verdict", "clean",
                     "status", "gate", "gated"}
        self.assertEqual(set(out.keys()) & forbidden, set())


class EpicCloseWrapsThreeAndNeverGates(unittest.TestCase):
    """IMP-7 pin: close_checks.py's own exit code is never a function of what the
    three checks found. Stubs stand in for attest.py and warrant.py so the pin holds
    independent of whichever half-finished state those two modules are in today."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "h"
        self.root.mkdir()
        self.stub_bin = pathlib.Path(self._tmp.name) / "bin"
        self.stub_bin.mkdir()
        self._real_here = cc.HERE
        cc.HERE = self.stub_bin
        self.addCleanup(setattr, cc, "HERE", self._real_here)

    def _install_stub(self, name, exit_code, payload):
        path = self.stub_bin / name
        path.write_text(
            "import json, sys\n"
            f"print(json.dumps({payload!r}))\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8")
        return path

    def test_a_fork_and_an_orphan_and_an_anomalous_act_all_present_exit_stays_0(self):
        self._install_stub("attest.py", 2, [{"name": "orso", "prev": "x",
                                             "branches": []}])
        self._install_stub("warrant.py", 3, {"orphans": [{"kind": "colegiado",
                                                           "id": "x"}], "clean": False})
        _write_act(self.root, "orso", 1)  # no matching event -> anomalous

        out = cc.epic_close(self.root)
        self.assertEqual(out["forks"]["exit_code"], 2)
        self.assertEqual(out["reconcile"]["exit_code"], 3)
        self.assertEqual(len(out["imp6"]["acts_anomalous"]), 1)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cc.main(["--root", str(self.root), "epic-close"])
        self.assertEqual(rc, 0, "a sub-tool's own exit code must never become this "
                               "tool's exit code (IMP-7)")
        printed = buf.getvalue()
        self.assertIn("ANOMALOUS", printed)
        self.assertIn("orso", printed)

    def test_even_a_sub_tool_that_cannot_run_at_all_leaves_exit_at_0(self):
        # No attest.py/warrant.py stub installed at all: python itself fails to find
        # the script and exits non-zero (2). _run_cli must record that, not raise, and
        # this tool's own exit code must stay 0 regardless (IMP-7).
        out = cc.epic_close(self.root)
        self.assertNotEqual(out["forks"]["exit_code"], 0)
        self.assertNotEqual(out["reconcile"]["exit_code"], 0)
        rc = cc.main(["--root", str(self.root), "epic-close"])
        self.assertEqual(rc, 0)

    def test_top_level_report_carries_no_verdict_field_of_its_own(self):
        out = cc.epic_close(self.root)
        for key in ("ok", "passed", "gate", "gated", "verdict"):
            self.assertNotIn(key, out)


class RealClis(unittest.TestCase):
    """Integration smoke tests against the actual attest.py and warrant.py CLIs."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "h"
        self.root.mkdir()

    def test_epic_close_runs_against_the_real_tools_on_an_empty_throwaway_root(self):
        out = cc.epic_close(self.root)
        self.assertIsNotNone(out["forks"]["exit_code"])
        self.assertIsNotNone(out["reconcile"]["exit_code"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cc.main(["--root", str(self.root), "epic-close"])
        self.assertEqual(rc, 0)

    def test_the_live_repo_runs_clean_through_the_cli(self):
        """Smoke test against the real, live .harness root: this must not crash on
        whatever acts/events/warrants exist there today."""
        r = subprocess.run([sys.executable, str(BIN_DIR / "close_checks.py"),
                            "epic-close"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("IMP-6", r.stdout)

    def test_json_mode_is_valid_json_with_the_three_sub_reports(self):
        r = subprocess.run([sys.executable, str(BIN_DIR / "close_checks.py"),
                            "--json", "epic-close"], capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(set(payload.keys()),
                         {"report", "IMP_7", "forks", "reconcile", "imp6"})

    def test_imp6_subcommand_alone_runs_against_the_live_repo(self):
        r = subprocess.run([sys.executable, str(BIN_DIR / "close_checks.py"),
                            "--json", "imp6"], capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("acts_total", payload)
        self.assertIn("act_signed_events", payload)


if __name__ == "__main__":
    unittest.main()
