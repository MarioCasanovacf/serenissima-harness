"""T-405: a verb that says, per validity condition, what it measured or that it cannot.

THE CLAIM IN THE TASK TITLE IS IMPRECISE AND IS CORRECTED HERE. "stale cannot evaluate
validity_conditions" is not what the implementation does, and the task required the claim be
evidenced rather than assumed, so it was read first and is recorded verbatim below:

    check V   evaluates only the two mechanically-checkable FORMS (V1-35): `path:N-M` and a
              bare path. A failing entry becomes a finding.
    V1-35     free-text entries are reported by `stale --json` as `"unchecked": true`,
              "never flagged, never an error" -- its own words.
    check D   decay candidates, which have nothing to do with validity conditions.

So stale DOES evaluate the checkable forms and DOES report the prose ones. THE GAP IS WHERE
THAT REPORT GOES. Measured against the live registry on 2026-08-19:

    text mode:  "stale: 34 reconsideration candidate(s) across 60 record(s)"
    --json:     64 entries carrying "unchecked": true, both of PR-022's among them

A reader in the default mode sees a clean candidate count with no signal that 64 conditions
were never evaluated at all. `conditions` is that missing view.

WHY NO VERDICT ON PROSE. The cost is asymmetric. A false lapse report on a tier-1 record
hands anyone who wants that record weakened a machine-generated reason to treat it as
expired, and PR-022 clause 4 is the strongest restraint in the layer. currency.py set the
precedent -- emit the figure, refuse the verdict.

Each group below carries a NEGATIVE CONTROL, because an assertion that everything is marked
NOT MECHANICALLY EVALUABLE passes just as well on a tool that marks everything that way.
"""
import ast
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / ".harness" / "bin" / "precedent.py"
LIVE_REGISTRY = ROOT / ".harness" / "precedents"
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import precedent  # noqa: E402


def record(pr_id, conditions, status="active", tier=2):
    return {
        "id": pr_id, "title": "registro de prueba", "subject": "prueba", "status": status,
        "authority_tier": tier, "ratio": "una regla que obliga",
        "scope_conditions": [], "validity_conditions": list(conditions),
        "revisit_trigger": "al vencer el warrant",
        "relations": [], "cites": [], "dicta": [],
        "interpretive_code_version": "v1", "declared_width": "narrow",
        "operation": "determination", "issuing_task": "T-000",
        "tier_evidence": ["T-000"], "confirmation_status": "unconfirmed",
        "sources": ["prueba"],
    }


class Registry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.reg = pathlib.Path(self._tmp.name) / "precedents"
        self.reg.mkdir(parents=True)

    def write(self, pr_id, conditions, **kw):
        rec = record(pr_id, conditions, **kw)
        (self.reg / (pr_id + ".json")).write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return rec

    def report(self):
        records = dict(precedent.scan_registry(self.reg))
        return precedent.validity_report(records)

    def cli(self, *argv):
        return subprocess.run([sys.executable, str(CLI), "conditions", "--root", str(self.reg)]
                              + list(argv), capture_output=True, text=True)

    def conditions_of(self, out, pr_id):
        row = next(r for r in out["by_record"] if r["record"] == pr_id)
        return row["conditions"]


class TheDisposition(Registry):
    """Every condition gets a measured value or the literal, and never both."""

    def test_prose_is_reported_and_not_judged(self):
        self.write("PR-001", ["mientras el gate siga abierto"])
        row = self.conditions_of(self.report(), "PR-001")[0]
        self.assertEqual(row["disposition"], precedent.NOT_EVALUABLE)
        self.assertIsNone(row["holds"], "a prose condition must carry no verdict at all")
        self.assertEqual(row["form"], "free-text")

    def test_a_checkable_condition_carries_a_measured_value(self):
        target = self.reg / "objetivo.txt"
        target.write_text("una linea\n", encoding="utf-8")
        # V1-35's bare-path form is `path:<ruta>`; a naked path is free text, which is
        # itself worth knowing and is why this test spells the prefix out.
        self.write("PR-001", ["path:" + str(target)])
        row = self.conditions_of(self.report(), "PR-001")[0]
        self.assertNotEqual(row["disposition"], precedent.NOT_EVALUABLE)
        self.assertTrue(row["holds"])
        self.assertEqual(row["form"], "bare-path")

    def test_a_checkable_condition_that_fails_says_what_was_measured(self):
        self.write("PR-001", ["path:" + str(self.reg / "no-existe.txt")])
        row = self.conditions_of(self.report(), "PR-001")[0]
        self.assertFalse(row["holds"])
        self.assertIn("does not exist", row["disposition"])

    def test_NEGATIVE_CONTROL_the_literal_is_not_stamped_on_everything(self):
        """Without this, the first test passes on a tool that marks every condition
        unevaluable -- which would be a tool that stopped measuring."""
        target = self.reg / "objetivo.txt"
        target.write_text("una linea\n", encoding="utf-8")
        self.write("PR-001", ["prosa libre", "path:" + str(target)])
        rows = self.conditions_of(self.report(), "PR-001")
        dispositions = [r["disposition"] for r in rows]
        self.assertEqual(dispositions.count(precedent.NOT_EVALUABLE), 1)
        self.assertEqual(len({r["form"] for r in rows}), 2)


class TheCounts(Registry):
    """Raw AND distinct, per TELEMETRY-PROVENANCE-A."""

    def test_counts_are_reported_twice(self):
        self.write("PR-001", ["misma frase", "otra frase"])
        self.write("PR-002", ["misma frase"])
        out = self.report()
        self.assertEqual((out["conditions_raw"], out["conditions_distinct"]), (3, 2))
        self.assertEqual((out["not_evaluable_raw"], out["not_evaluable_distinct"]), (3, 2))

    def test_the_divergence_is_the_finding_not_an_artifact(self):
        """A sentence carried by several records goes stale in all of them at once. Reporting
        only the distinct count would hide how many records one lapse reaches."""
        for pr_id in ("PR-001", "PR-002", "PR-003"):
            self.write(pr_id, ["FORCE-IDENTITY-A sigue abierto"])
        out = self.report()
        self.assertEqual(out["conditions_raw"], 3)
        self.assertEqual(out["conditions_distinct"], 1)
        self.assertEqual(out["records_with_conditions_raw"], 3)

    def test_the_active_only_count_reconciles_against_stale(self):
        """`stale` skips non-active records. Without an active-only figure, a scope
        difference and a bug look identical from the outside."""
        self.write("PR-001", ["prosa activa"])
        self.write("PR-002", ["prosa superada"], status="superseded")
        out = self.report()
        self.assertEqual(out["not_evaluable_raw"], 2)
        self.assertEqual(out["not_evaluable_active_raw"], 1)

    def test_NEGATIVE_CONTROL_raw_and_distinct_actually_differ_somewhere(self):
        """A pair of counts that can never disagree is decoration. This pins a case where
        they must, so a change collapsing one into the other fails here."""
        self.write("PR-001", ["repetida", "repetida"])
        out = self.report()
        self.assertNotEqual(out["conditions_raw"], out["conditions_distinct"])


class TheRefusalToRule(Registry):
    """No pass/fail verdict on prose -- checked by parsing the module, not by grepping it.

    GUARD-MENTION-C, eighth occurrence: the module's own docstrings discuss verdicts,
    lapses and thresholds at length, and a substring scan cannot tell that prose from an
    assignment.
    """

    @staticmethod
    def function(name):
        tree = ast.parse(CLI.read_text(encoding="utf-8"))
        return next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == name)

    def test_the_free_text_branch_assigns_no_boolean_verdict(self):
        fn = self.function("validity_report")
        holds_values = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "holds":
                        holds_values.append(value)
        self.assertTrue(holds_values, "the report stopped carrying a `holds` field")
        constants = [v.value for v in holds_values if isinstance(v, ast.Constant)]
        self.assertIn(None, constants,
                      "no branch assigns holds=None, so some condition is being judged that "
                      "cannot be measured")

    def test_the_report_verb_always_exits_zero(self):
        """A report that sets an exit code is a check, and `stale` is already the check."""
        fn = self.function("cmd_conditions")
        returns = [n.value.value for n in ast.walk(fn)
                   if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)]
        self.assertEqual(set(returns), {0})

    def test_it_writes_nothing(self):
        fn = self.function("validity_report")
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and node.attr in (
                    "write_text", "write_bytes", "mkdir", "unlink", "rmdir", "touch"):
                self.fail("validity_report calls %s; it must be read-only" % node.attr)

    def test_NEGATIVE_CONTROL_the_ast_helper_finds_what_is_there(self):
        """A parser that silently matched nothing would pass every test above."""
        self.assertEqual(self.function("cmd_conditions").name, "cmd_conditions")
        with self.assertRaises(StopIteration):
            self.function("una_funcion_que_no_existe")

    def test_the_refusal_is_stated_in_the_output_and_not_only_in_the_code(self):
        self.write("PR-001", ["prosa"])
        out = self.report()
        self.assertIn("refuse the verdict", out["NO_VERDICT_ON_PROSE"])
        self.assertIn("PR-022", out["A_LAPSE_IN_LETTER_IS_NOT_A_LAPSE_IN_PURPOSE"])
        self.assertIn("T-404", out["A_LAPSE_IN_LETTER_IS_NOT_A_LAPSE_IN_PURPOSE"])


class AgainstTheLiveRegistry(unittest.TestCase):
    """T-404's finding has to be visible in the output, not only in a task file."""

    def setUp(self):
        if not LIVE_REGISTRY.is_dir():
            self.skipTest("no live registry in this checkout")
        self.out = precedent.validity_report(dict(precedent.scan_registry(LIVE_REGISTRY)))

    def test_PR_022s_lapsed_condition_is_listed_and_marked_unevaluable(self):
        rows = next(r for r in self.out["by_record"] if r["record"] == "PR-022")["conditions"]
        texts = [r["condition"] for r in rows]
        self.assertIn(
            "FORCE-IDENTITY-A is open: no cryptographic identity with an external trust "
            "root exists in this harness", texts)
        for row in rows:
            self.assertEqual(row["disposition"], precedent.NOT_EVALUABLE)
            self.assertIsNone(row["holds"])

    def test_the_active_count_matches_what_stale_reports_unchecked(self):
        """The two tools have to agree or one of them is wrong, and the report says which
        figure is the comparable one."""
        proc = subprocess.run([sys.executable, str(CLI), "stale", "--json",
                               "--root", str(LIVE_REGISTRY)], capture_output=True, text=True)
        unchecked = [f for f in json.loads(proc.stdout) if f.get("unchecked")]
        self.assertEqual(self.out["not_evaluable_active_raw"], len(unchecked))

    def test_NEGATIVE_CONTROL_the_live_registry_is_not_uniformly_prose(self):
        """If every live condition were free text, the PR-022 assertion above would prove
        nothing about the classifier."""
        self.assertGreater(self.out["evaluable_raw"], 0)
        self.assertGreater(self.out["not_evaluable_raw"], 0)


class TheCli(Registry):
    def test_text_mode_names_both_counts_and_the_literal(self):
        self.write("PR-001", ["prosa"])
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(precedent.NOT_EVALUABLE, proc.stdout)
        self.assertIn("crudas", proc.stdout)
        self.assertIn("distintas", proc.stdout)

    def test_json_mode_is_parseable_and_carries_the_refusal(self):
        self.write("PR-001", ["prosa"])
        proc = self.cli("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIn("NO_VERDICT_ON_PROSE", out)
        self.assertEqual(out["by_record"][0]["conditions"][0]["disposition"],
                         precedent.NOT_EVALUABLE)

    def test_a_registry_with_no_conditions_at_all_still_reports(self):
        """An empty result is a fact. A verb that printed nothing would be
        indistinguishable from a verb that failed."""
        self.write("PR-001", [])
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("0 crudas", proc.stdout)


if __name__ == "__main__":
    unittest.main()
