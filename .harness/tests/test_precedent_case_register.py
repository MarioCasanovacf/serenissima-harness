"""test_precedent_case_register.py -- tests for T-412 / S-1 Case Register.

Verifies:
  1. `case open` opens C-001, C-002, ... and refuses empty question/task.
  2. `case list` and `case show` report cases accurately with json support.
  3. `publish` requires a registered, open case (--case C-NNN), stores it in PR-NNN,
     and marks the case disposed (verb=publish).
  4. `distinguish` requires a registered, open case (--case C-NNN), and marks the case
     disposed (verb=distinguish).
  5. Second disposal of a case is refused on both verbs (no silent overwrites).
  6. `disposition-ratio` separates pre-register from registered legislation, counts
     still-open cases in denominator, never folds pre-register into the share, and
     preserves disclaimers.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / ".harness" / "bin" / "precedent.py"
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import attest  # noqa: E402
import precedent  # noqa: E402
from test_attest_intent import Enrolled  # noqa: E402

FACTS = ("El caso presenta un agente delegado sin plaza, y el registro citado solo alcanza "
         "nombres con warrant, por lo que su alcance declarado no cubre estos hechos.")


class CaseRegisterFixture(Enrolled):

    def setUp(self):
        super().setUp()
        self.reg = self.root / "precedents"
        self.reg.mkdir(parents=True, exist_ok=True)
        self.cases_dir = self.root / "cases"

    def cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(argv) +
            ["--root", str(self.reg), "--harness-root", str(self.root)],
            capture_output=True, text=True)

    def write_pr(self, pr_id, scope=None, status="active", published_at=None, case=None):
        rec = {
            "id": pr_id, "title": "registro " + pr_id, "subject": "prueba", "status": status,
            "authority_tier": 2, "ratio": "una regla que obliga",
            "scope_conditions": scope if scope is not None else ["aplica a pruebas"],
            "validity_conditions": ["mientras el gate siga abierto"],
            "revisit_trigger": "al vencer el warrant",
            "relations": [], "cites": [], "dicta": [],
            "interpretive_code_version": "v1", "declared_width": "narrow",
            "operation": {"type": "determination", "subtype": None},
            "issuing_task": "T-000", "tier_evidence": ["T-000"],
            "confirmation_status": "unconfirmed", "sources": ["prueba"],
            "published_at": published_at or "2026-08-01T00:00:00Z",
            "case": case,
        }
        (self.reg / (pr_id + ".json")).write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return rec

    def open_case(self, question="cual es la regla", task="T-100", agent="worker-a"):
        return self.cli("case", "open", "--question", question, "--task", task, "--agent", agent)

    def intent(self, name="orso", task="T-1"):
        return attest.declare_intent(self.root, name, self.keys[name], "distinguish", task,
                                     "dispongo del caso citando PR-001")


class CaseOpenTests(CaseRegisterFixture):

    def test_open_case_creates_c001_and_increments(self):
        r1 = self.open_case("pregunta 1", "T-1")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertIn("opened case C-001", r1.stdout)
        c1_file = self.cases_dir / "C-001.json"
        self.assertTrue(c1_file.exists())
        c1 = json.loads(c1_file.read_text(encoding="utf-8"))
        self.assertEqual(c1["id"], "C-001")
        self.assertEqual(c1["question"], "pregunta 1")
        self.assertEqual(c1["task"], "T-1")
        self.assertEqual(c1["status"], "open")
        self.assertIsNone(c1["disposal"])

        r2 = self.open_case("pregunta 2", "T-2")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("opened case C-002", r2.stdout)
        self.assertTrue((self.cases_dir / "C-002.json").exists())

    def test_open_case_refuses_empty_question_or_task(self):
        r1 = self.open_case("   ", "T-1")
        self.assertEqual(r1.returncode, 1)
        self.assertIn("question must be non-empty", r1.stderr)

        r2 = self.cli("case", "open", "--question", "valida", "--task", "   ")
        self.assertEqual(r2.returncode, 1)
        self.assertIn("task must be non-empty", r2.stderr)

    def test_case_list_and_show(self):
        self.open_case("pregunta 1", "T-1")
        self.open_case("pregunta 2", "T-2")

        r_list = self.cli("case", "list", "--json")
        self.assertEqual(r_list.returncode, 0, r_list.stderr)
        items = json.loads(r_list.stdout)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "C-001")
        self.assertEqual(items[1]["id"], "C-002")

        r_show = self.cli("case", "show", "C-001", "--json")
        self.assertEqual(r_show.returncode, 0, r_show.stderr)
        item = json.loads(r_show.stdout)
        self.assertEqual(item["id"], "C-001")
        self.assertEqual(item["question"], "pregunta 1")

        r_missing = self.cli("case", "show", "C-999")
        self.assertEqual(r_missing.returncode, 1)


class PublishCaseIntegrationTests(CaseRegisterFixture):

    def publish_cmd(self, case_id=None, task="T-100", title="Titulo", subject="prueba",
                    tier=3, ratio="ratio text", sources="T-100"):
        argv = ["publish", "--task", task, "--title", title, "--subject", subject,
                "--tier", str(tier), "--ratio", ratio, "--width", "narrow",
                "--sources", sources, "--code-version", "v1",
                "--tier-evidence", task, "--scope", "role:worker",
                "--revisit-trigger", "revisit", "--validity", "condicion"]
        if case_id is not None:
            argv += ["--case", case_id]
        return self.cli(*argv)

    def test_publish_without_case_is_refused(self):
        r = self.publish_cmd()
        self.assertEqual(r.returncode, 1)
        self.assertIn("--case is required", r.stderr)

    def test_publish_with_unregistered_case_is_refused(self):
        r = self.publish_cmd(case_id="C-999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not registered", r.stderr)

    def test_publish_with_invalid_case_format_is_refused(self):
        r = self.publish_cmd(case_id="T-100")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a valid case id format", r.stderr)

    def test_publish_succeeds_and_disposes_case(self):
        self.open_case("como regular X", "T-1")
        r = self.publish_cmd(case_id="C-001")
        self.assertEqual(r.returncode, 0, r.stderr)

        # Check PR-001 record has case
        pr_data = json.loads((self.reg / "PR-001.json").read_text(encoding="utf-8"))
        self.assertEqual(pr_data.get("case"), "C-001")

        # Check C-001 is disposed
        c1 = json.loads((self.cases_dir / "C-001.json").read_text(encoding="utf-8"))
        self.assertEqual(c1["status"], "disposed")
        self.assertEqual(c1["disposal"]["verb"], "publish")
        self.assertEqual(c1["disposal"]["ref"], "PR-001")

    def test_second_disposal_of_case_via_publish_is_refused(self):
        self.open_case("pregunta", "T-100")
        r1 = self.publish_cmd(case_id="C-001", task="T-100", title="PR1")
        self.assertEqual(r1.returncode, 0, r1.stderr)

        r2 = self.publish_cmd(case_id="C-001", task="T-101", title="PR2")
        self.assertEqual(r2.returncode, 1)
        self.assertIn("already disposed", r2.stderr)


class DistinguishCaseIntegrationTests(CaseRegisterFixture):

    def setUp(self):
        super().setUp()
        self.write_pr("PR-001", scope=["aplica solo a nombres con warrant vigente"])

    def distinguish_cmd(self, case_id=None, nearest="PR-001", facts=FACTS, name="orso", task="T-1"):
        argv = ["distinguish", "--nearest", nearest, "--facts", facts,
                "--by", name, "--key", str(self.keys[name]), "--task", task]
        if case_id is not None:
            argv += ["--case", case_id]
        return self.cli(*argv)

    def test_distinguish_without_case_is_refused(self):
        self.intent()
        r = self.distinguish_cmd()
        self.assertEqual(r.returncode, 1)
        self.assertIn("--case is required", r.stderr)

    def test_distinguish_with_unregistered_case_is_refused(self):
        self.intent()
        r = self.distinguish_cmd(case_id="C-999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not registered", r.stderr)

    def test_distinguish_succeeds_and_disposes_case(self):
        self.open_case("aplica PR-001?", "T-1")
        self.intent()
        r = self.distinguish_cmd(case_id="C-001")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("distinguished C-001 by citing PR-001", r.stdout)

        c1 = json.loads((self.cases_dir / "C-001.json").read_text(encoding="utf-8"))
        self.assertEqual(c1["status"], "disposed")
        self.assertEqual(c1["disposal"]["verb"], "distinguish")

    def test_second_disposal_via_distinguish_is_refused(self):
        self.open_case("aplica PR-001?", "T-1")
        self.intent()
        r1 = self.distinguish_cmd(case_id="C-001")
        self.assertEqual(r1.returncode, 0, r1.stderr)

        self.intent()
        r2 = self.distinguish_cmd(case_id="C-001")
        self.assertEqual(r2.returncode, 1)
        self.assertIn("already disposed", r2.stderr)


class DispositionRatioCaseRegisterTests(CaseRegisterFixture):

    def test_pre_register_bucket_and_registered_share(self):
        # 2 legacy records before C-001 exists
        self.write_pr("PR-001", published_at="2026-08-01T00:00:00Z")
        self.write_pr("PR-002", published_at="2026-08-02T00:00:00Z")

        # Open C-001 and C-002
        self.open_case("caso 1", "T-1")
        self.open_case("caso 2", "T-2")

        # Distinguish C-001
        self.intent()
        r_dist = self.cli("distinguish", "--case", "C-001", "--nearest", "PR-001",
                          "--facts", FACTS, "--by", "orso",
                          "--key", str(self.keys["orso"]), "--task", "T-1")
        self.assertEqual(r_dist.returncode, 0, r_dist.stderr)

        # C-002 remains open

        out = precedent.disposition_counts(self.reg, self.root)
        self.assertEqual(out["cases_opened_raw"], 2)
        self.assertEqual(out["cases_still_open_raw"], 1)
        self.assertEqual(out["by_citation_raw"], 1)
        self.assertEqual(out["by_legislation_pre_register_raw"], 2)
        self.assertEqual(out["by_legislation_registered_raw"], 0)
        self.assertEqual(out["registered_dispositions_raw"], 1)
        # Citation share of registered dispositions = 1 / (1 + 0) = 1.0 (100%)
        self.assertEqual(out["citation_share_of_dispositions"], 1.0)
        # But pre-register count is preserved separately
        self.assertEqual(out["published_before_register_raw"], 2)

        # Print output check
        r_ratio = self.cli("disposition-ratio")
        self.assertEqual(r_ratio.returncode, 0, r_ratio.stderr)
        self.assertIn("casos abiertos             2 crudos", r_ratio.stdout)
        self.assertIn("dispuestos por cita        1 crudos", r_ratio.stdout)
        self.assertIn("aun abiertos               1 crudos", r_ratio.stdout)
        self.assertIn("publicados pre-registro    2 crudos", r_ratio.stdout)
        self.assertIn("The denominator is cases REGISTERED, not cases ARISING", r_ratio.stdout)


if __name__ == "__main__":
    unittest.main()
