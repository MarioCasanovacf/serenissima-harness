"""test_precedent_case_publisher_report.py -- T-428 item 5.

Verifies the read-only `case publisher-report` verb and its `classify_seat`
helper in precedent.py:
  1. classify_seat classifies clerk / issued-non-clerk / unissued / no-roster
     / roster-inconsistent, mirroring deliberate.py's assembly_eligibility
     but never refusing anything.
  2. `case publisher-report` reports, for a --case, whether the disposing
     record's published_by is a clerk seat, an issued non-clerk name, or
     unissued -- report only, never a refusal of `publish` itself.
  3. `publish` carries NO clerk gate: a clerk-seated --agent still publishes
     successfully (negative control for item 5's explicit "do NOT add a
     clerk gate to precedent.py publish").
  4. CLERK_MARKERS is pinned identical to deliberate.py's CLERK_MARKERS so
     the two modules cannot silently drift apart.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / ".harness" / "bin" / "precedent.py"
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import deliberate  # noqa: E402
import harness_common as hc  # noqa: E402
import precedent  # noqa: E402

CHARTER = ("integridad del proceso; NO legisla, NO vota, NO tiene stake "
           "(AgentCity clerk constraint)")


class ClerkMarkersDoNotDrift(unittest.TestCase):
    """The two modules define CLERK_MARKERS independently (importing one
    from the other would create a circular import: deliberate.py already
    imports precedent.py for item 4's case-linkage check). This test is the
    mechanical guard against the two constants silently diverging."""

    def test_the_two_modules_agree_on_the_clerk_markers(self):
        self.assertEqual(precedent.CLERK_MARKERS, deliberate.CLERK_MARKERS)


class ClassifySeatUnitTests(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.hroot = pathlib.Path(self._tmp.name)

    def write_roster(self, roster):
        (self.hroot / "roster.json").write_text(json.dumps(roster), encoding="utf-8")

    def base_roster(self):
        return {
            "schema_version": 1,
            "colegiados": {
                "fedatario": {"incentive": CHARTER},
                "registro": {"incentive": "registros confirmados que sobreviven"},
            },
            "names": {
                "fed-relator": {"colegiado": "fedatario", "role": "relator"},
                "registro-a": {"colegiado": "registro", "role": "author"},
            },
        }

    def test_no_roster_at_all(self):
        self.assertEqual(precedent.classify_seat(self.hroot, "anybody"), "no-roster")

    def test_clerk_seat(self):
        self.write_roster(self.base_roster())
        self.assertEqual(precedent.classify_seat(self.hroot, "fed-relator"), "clerk")

    def test_issued_non_clerk(self):
        self.write_roster(self.base_roster())
        self.assertEqual(precedent.classify_seat(self.hroot, "registro-a"), "issued-non-clerk")

    def test_unissued_name(self):
        self.write_roster(self.base_roster())
        self.assertEqual(precedent.classify_seat(self.hroot, "ghost"), "unissued")

    def test_empty_or_none_name_is_unissued(self):
        self.write_roster(self.base_roster())
        self.assertEqual(precedent.classify_seat(self.hroot, ""), "unissued")
        self.assertEqual(precedent.classify_seat(self.hroot, None), "unissued")

    def test_orphan_colegiado_is_roster_inconsistent(self):
        roster = self.base_roster()
        del roster["colegiados"]["fedatario"]
        self.write_roster(roster)
        self.assertEqual(precedent.classify_seat(self.hroot, "fed-relator"), "roster-inconsistent")

    def test_no_charter_text_is_roster_inconsistent(self):
        roster = self.base_roster()
        roster["colegiados"]["registro"]["incentive"] = ""
        self.write_roster(roster)
        self.assertEqual(precedent.classify_seat(self.hroot, "registro-a"), "roster-inconsistent")

    def test_unreadable_roster_is_roster_inconsistent(self):
        (self.hroot / "roster.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(precedent.classify_seat(self.hroot, "anybody"), "roster-inconsistent")

    def test_a_college_is_a_clerk_by_charter_not_by_name(self):
        """Same rule as deliberate.py: the marker is read from the DECLARED
        charter text, not a hardcoded college name."""
        roster = self.base_roster()
        roster["colegiados"]["notariado"] = {"incentive": CHARTER}
        roster["names"]["not-1"] = {"colegiado": "notariado", "role": "x"}
        self.write_roster(roster)
        self.assertEqual(precedent.classify_seat(self.hroot, "not-1"), "clerk")


class PublisherReportFixture(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.hroot = pathlib.Path(self._tmp.name)
        self.reg = self.hroot / "precedents"
        self.reg.mkdir(parents=True)
        self.cases_dir = self.hroot / "cases"
        roster = {
            "schema_version": 1,
            "colegiados": {
                "fedatario": {"incentive": CHARTER},
                "registro": {"incentive": "registros confirmados que sobreviven"},
            },
            "names": {
                "fed-codificador": {"colegiado": "fedatario", "role": "codificador"},
                "registro-a": {"colegiado": "registro", "role": "author"},
            },
        }
        (self.hroot / "roster.json").write_text(json.dumps(roster), encoding="utf-8")

    def cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(argv) +
            ["--root", str(self.reg), "--harness-root", str(self.hroot)],
            capture_output=True, text=True)

    def open_case(self, question="q", task="T-1"):
        r = self.cli("case", "open", "--question", question, "--task", task,
                     "--agent", "worker-x")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.split()[2].rstrip(":")

    def publish(self, case_id, agent, title="Titulo"):
        argv = ["publish", "--task", "T-100", "--title", title, "--subject", "prueba",
                "--tier", "3", "--ratio", "una regla", "--width", "narrow",
                "--sources", "T-100", "--code-version", "v1",
                "--tier-evidence", "T-100", "--scope", "role:worker",
                "--revisit-trigger", "revisit", "--validity", "condicion",
                "--agent", agent, "--case", case_id]
        return self.cli(*argv)

    def report(self, case_id, as_json=True):
        argv = ["case", "publisher-report", case_id]
        if as_json:
            argv.append("--json")
        return self.cli(*argv)


class PublisherReportTests(PublisherReportFixture):

    def test_report_on_an_open_case_notes_no_disposing_record(self):
        cid = self.open_case()
        r = self.report(cid)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["case_status"], "open")
        self.assertIsNone(out["classification"])
        self.assertIn("still open", out["note"])

    def test_report_on_an_unknown_case_is_refused(self):
        r = self.report("C-999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not found", r.stderr)

    def test_publish_carries_no_clerk_gate_and_the_report_classifies_it_clerk(self):
        """Negative control for item 5: `publish` must NOT refuse a
        clerk-seated --agent. W-002 assigns fed-codificador that office; the
        contradiction with the clerk charter is a docket's business, not
        this tool's."""
        cid = self.open_case()
        r_pub = self.publish(cid, agent="fed-codificador")
        self.assertEqual(r_pub.returncode, 0, r_pub.stderr)

        r = self.report(cid)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["disposal_verb"], "publish")
        self.assertEqual(out["record_id"], "PR-001")
        self.assertEqual(out["published_by"], "fed-codificador")
        self.assertEqual(out["classification"], "clerk")

    def test_report_classifies_an_issued_non_clerk_publisher(self):
        cid = self.open_case()
        r_pub = self.publish(cid, agent="registro-a")
        self.assertEqual(r_pub.returncode, 0, r_pub.stderr)
        r = self.report(cid)
        out = json.loads(r.stdout)
        self.assertEqual(out["published_by"], "registro-a")
        self.assertEqual(out["classification"], "issued-non-clerk")

    def test_report_classifies_an_unissued_publisher(self):
        cid = self.open_case()
        r_pub = self.publish(cid, agent="nobody-in-the-roster")
        self.assertEqual(r_pub.returncode, 0, r_pub.stderr)
        r = self.report(cid)
        out = json.loads(r.stdout)
        self.assertEqual(out["published_by"], "nobody-in-the-roster")
        self.assertEqual(out["classification"], "unissued")

    def test_report_on_a_case_disposed_by_distinguish_notes_no_record(self):
        """`distinguish` writes no precedent record, so there is no
        published_by to classify -- the report says so rather than
        crashing or fabricating a classification."""
        cid = self.open_case()
        case_path = self.cases_dir / (cid + ".json")
        data = json.loads(case_path.read_text(encoding="utf-8"))
        data["status"] = "disposed"
        data["disposal"] = {"verb": "distinguish", "ref": "orso_1", "by": "orso",
                            "task": "T-1", "ts": hc.now_iso()}
        case_path.write_text(json.dumps(data), encoding="utf-8")

        r = self.report(cid)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["disposal_verb"], "distinguish")
        self.assertIsNone(out["classification"])
        self.assertIn("distinguish", out["note"])

    def test_human_readable_output_is_not_json(self):
        cid = self.open_case()
        self.publish(cid, agent="registro-a")
        r = self.report(cid, as_json=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("publisher report", r.stdout)
        self.assertIn("issued-non-clerk", r.stdout)


if __name__ == "__main__":
    unittest.main()
