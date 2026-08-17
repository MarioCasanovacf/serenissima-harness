"""T-403 / D4b: the PR-029 reconciliation-cost KPI, whose correct output today is a REFUSAL.

PR-029's dicta are empty, so every clause is ratio and binds. Clause 6, verbatim:

    "The metric is measurable only once two domain registries exist; until then it is
     recorded as not yet measurable with that reason, never as zero."

One domain registry exists. So a tool that printed 0 hours and 0 tokens would VIOLATE A
TIER-1 RATIO while appearing to work, and the harm is specific rather than pedantic: a zero
reads as "divergence repair is free", which is clause 5's first branch, which concludes Part
C's containment architecture is over-engineered and should be SIMPLIFIED. A fabricated zero
here argues for dismantling the containment layer from a measurement never taken.

So most of this file tests that the tool REFUSES, and that it refuses for the reason clause 6
requires be recorded rather than merely declining. The rest tests the two conflations that
would produce a false figure:

  - zero MEASUREMENTS taken versus zero COST, which clause 6 legislates against directly;
  - the definition of "domain registry", which PR-029 does not supply. That definition is the
    switch controlling whether the refusal applies at all, so widening it is a cheaper route
    to a "measurable" KPI than building a second registry. It is therefore the tool's own
    definition, labelled as such, and printed on every run so it can be argued with.
"""
import ast
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / ".harness" / "bin" / "westphalia_kpi.py"
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import westphalia_kpi as kpi  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "h"
        (self.root / "precedents").mkdir(parents=True)
        self.add_registry("precedents", "PR-", 3)

    def add_registry(self, name, prefix, n):
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        for i in range(1, n + 1):
            (d / "{}{:03d}.json".format(prefix, i)).write_text(
                json.dumps({"id": "{}{:03d}".format(prefix, i)}) + "\n", encoding="utf-8")

    def cli(self, *argv):
        return subprocess.run([sys.executable, str(CLI), "--root", str(self.root)] +
                              list(argv), capture_output=True, text=True)


class TheRefusal(Fixture):

    def test_the_status_is_not_yet_measurable(self):
        out = kpi.report(self.root)
        self.assertEqual(out["status"], kpi.NOT_MEASURABLE)

    def test_no_cost_figure_is_emitted(self):
        out = kpi.report(self.root)
        self.assertIsNone(out["cost"])

    def test_the_refusal_carries_the_reason_clause_6_requires(self):
        """Clause 6 does not merely permit declining: it requires the metric be recorded as
        not measurable WITH THAT REASON. A bare 'unavailable' would not comply."""
        why = kpi.report(self.root)["WHY_NO_FIGURE"]
        self.assertIn("never as zero", why)
        self.assertIn("only one domain registry exists", why)
        self.assertIn("nothing to reconcile against", why)

    def test_the_refusal_states_the_harm_of_a_zero(self):
        # Because "why not just print 0" is the obvious next question, and the answer is not
        # tidiness: a zero argues for dismantling Part C.
        why = kpi.report(self.root)["WHY_NO_FIGURE"]
        self.assertIn("divergence repair is free", why)
        self.assertIn("SIMPLIFYING", why)
        self.assertIn("never taken", why)

    def test_the_word_zero_never_appears_as_a_cost_in_the_rendered_output(self):
        r = self.cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NO EMITIDO", r.stdout)
        self.assertIn("NOT YET MEASURABLE", r.stdout)

    def test_no_verdict_is_emitted_because_clause_5_defines_no_threshold(self):
        out = kpi.report(self.root)
        note = out["NO_THRESHOLD_RATIFIED"]
        self.assertIn("no failing point", note)
        self.assertIn("currency.py", note)
        for forbidden in ("pass", "fail", "PASS", "FAIL", "healthy", "unhealthy"):
            self.assertNotIn(forbidden, str(out.get("status")))


class TheTwoConflations(Fixture):

    def test_zero_measurements_is_not_zero_cost(self):
        out = kpi.report(self.root)
        self.assertEqual(out["measurements_raw"], 0)
        self.assertIsNone(out["cost"], "an empty measurement set became a cost of zero")
        self.assertIn("It is NOT the cost", out["A_COUNT_OF_ZERO_IS_NOT_A_COST_OF_ZERO"])

    def test_the_registry_definition_is_attributed_to_the_tool_not_the_record(self):
        """PR-029 does not define 'domain registry'. Presenting the tool's operationalization
        as the record's would be a miscitation of a tier-1 ratio."""
        out = kpi.report(self.root)
        note = out["THIS_DEFINITION_IS_THE_TOOLS_NOT_THE_RECORDS"]
        self.assertIn("PR-029 does not define", note)
        self.assertIn("contestable", note)
        # and it must say WHY it is printed: because widening it is the cheap way to fake
        # measurability, so it has to stay visible
        self.assertIn("cheaper way", note)

    def test_the_definition_is_printed_on_every_run(self):
        r = self.cli()
        self.assertIn("PR-029 does not define", r.stdout)


class ThePrecondition(Fixture):

    def test_one_registry_is_not_enough(self):
        self.assertEqual(kpi.report(self.root)["registries_distinct"], 1)
        self.assertEqual(kpi.report(self.root)["status"], kpi.NOT_MEASURABLE)

    def test_an_empty_directory_is_not_a_registry(self):
        (self.root / "domains").mkdir()
        self.assertEqual(kpi.domain_registries(self.root)["registries_raw"], 1)

    def test_counts_are_reported_raw_and_distinct(self):
        out = kpi.report(self.root)
        for stem in ("registries", "measurements"):
            self.assertIn(stem + "_raw", out)
            self.assertIn(stem + "_distinct", out)

    def test_the_measurement_store_is_not_created_on_read(self):
        """A tool that made its own empty store would make 'the store is empty'
        indistinguishable from 'the store was never set up'. Different facts."""
        mes = kpi.measurements(self.root)
        self.assertFalse(mes["store_exists"])
        self.assertFalse(pathlib.Path(mes["store"]).exists())

    def test_a_recorded_measurement_is_counted_but_still_yields_no_cost(self):
        """Even a measurement on file does not unlock a cost while clause 6's precondition is
        unmet. The precondition is about registries, not about paperwork."""
        d = self.root / "kpi" / "westphalia"
        d.mkdir(parents=True)
        (d / "2026Q3.json").write_text(
            json.dumps({"quarter": "2026Q3", "hours": 40, "tokens": 1200000}) + "\n",
            encoding="utf-8")
        out = kpi.report(self.root)
        self.assertEqual(out["measurements_raw"], 1)
        self.assertEqual(out["status"], kpi.NOT_MEASURABLE)
        self.assertIsNone(out["cost"])

    def test_an_unparseable_measurement_is_reported_not_skipped(self):
        d = self.root / "kpi" / "westphalia"
        d.mkdir(parents=True)
        (d / "bad.json").write_text("{not json", encoding="utf-8")
        mes = kpi.measurements(self.root)
        self.assertEqual(len(mes["unparseable"]), 1)
        self.assertEqual(mes["measurements_distinct"], 0)


class WhenTwoRegistriesExist(Fixture):
    """The forward case, so the refusal is a CONDITION and not a hardcoded constant.

    A tool that always refused would pass every test above while being useless. This class is
    what distinguishes "refuses because the precondition is unmet" from "refuses".
    """

    def setUp(self):
        super().setUp()
        # A second registry the current definition does not recognise. It must NOT flip the
        # precondition, because the definition is deliberately narrow -- and this is the test
        # that would fail first if someone widened it to fake measurability.
        self.add_registry("domains", "DR-", 2)

    def test_a_registry_outside_the_declared_definition_does_not_flip_the_precondition(self):
        out = kpi.report(self.root)
        self.assertEqual(out["registries_distinct"], 1)
        self.assertEqual(out["status"], kpi.NOT_MEASURABLE)

    def test_the_precondition_does_flip_when_the_definition_recognises_two(self):
        """Monkeypatched at the definition, which is the only place that should decide this."""
        real = kpi.domain_registries

        def widened(root):
            out = real(root)
            out["registries_raw"] += 1
            out["registries_distinct"] += 1
            out["registries"].append({"name": "domains", "prefix": "DR-", "records": 2})
            return out

        kpi.domain_registries = widened
        self.addCleanup(setattr, kpi, "domain_registries", real)
        out = kpi.report(self.root)
        self.assertNotEqual(out["status"], kpi.NOT_MEASURABLE)
        # AND STILL NO COST. Clause 3 requires hours PLUS tokens and wall-clock is not
        # instrumented, so meeting the precondition does not manufacture a measurement.
        self.assertIsNone(out["cost"])
        self.assertIn("wall-clock half is not instrumented", out["WHY_NO_FIGURE"])


class TheInstrumentationGap(Fixture):

    def test_wall_clock_is_reported_as_uninstrumented_rather_than_dropped(self):
        inst = kpi.report(self.root)["instrumentation"]
        self.assertIn("NOT INSTRUMENTED", inst["wall_clock_hours"])
        self.assertIn("half-blind", inst["wall_clock_hours"])

    def test_tokens_are_reported_as_partial_with_the_harvester_caveat(self):
        inst = kpi.report(self.root)["instrumentation"]
        self.assertIn("PARTIAL", inst["tokens"])
        self.assertIn("harvester", inst["tokens"])
        self.assertIn("cache split", inst["tokens"])

    def test_both_clause_3_components_are_named(self):
        out = kpi.report(self.root)
        self.assertEqual(out["measure_required_by_clause_3"],
                         ["wall_clock_hours", "tokens"])


class TheModuleCannotFabricateACost(unittest.TestCase):
    """The structural guard, parsed rather than scanned.

    A substring scan is wrong here for the reason on this project's register five times over
    (GUARD-MENTION-C): the module's prose repeatedly discusses zero, cost and thresholds, and a
    scan cannot tell that prose from an assignment. So this walks the AST.
    """

    @staticmethod
    def tree():
        return ast.parse(CLI.read_text(encoding="utf-8"))

    def test_no_assignment_ever_puts_a_number_in_cost(self):
        for node in ast.walk(self.tree()):
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "cost"):
                    self.assertIsInstance(node.value, ast.Constant,
                                          "out['cost'] is assigned a computed value")
                    self.assertIsNone(node.value.value,
                                      "out['cost'] is assigned something other than None")

    def test_the_module_does_no_arithmetic_on_hours_or_tokens(self):
        """It reports what is instrumented; it must not quietly compute a cost from whatever
        it can reach. A BinOp over a name containing 'hour' or 'token' would be that."""
        for node in ast.walk(self.tree()):
            if not isinstance(node, ast.BinOp):
                continue
            names = [n.id.lower() for n in ast.walk(node) if isinstance(n, ast.Name)]
            for bad in ("hour", "token", "cost"):
                self.assertFalse(any(bad in n for n in names),
                                 "arithmetic over %r found in the KPI module" % bad)

    def test_it_reads_and_never_writes(self):
        """Read-only, enforced structurally. A KPI that can write is a KPI that can record a
        measurement nobody took."""
        for node in ast.walk(self.tree()):
            if isinstance(node, ast.Attribute) and node.attr in (
                    "write_text", "write_bytes", "mkdir", "unlink", "rmdir", "touch"):
                self.fail("the KPI module calls %s; it must be read-only" % node.attr)

    def test_the_ratio_it_relies_on_is_quoted_in_the_docstring(self):
        doc = kpi.__doc__ or ""
        self.assertIn("never as zero", doc)
        self.assertIn("NOT YET MEASURABLE", doc)
        self.assertIn("NO THRESHOLD RATIFIED", doc)
        self.assertIn("dicta", doc, "the docstring must say why every clause binds")


class ThePublishedRecordStillSaysThis(unittest.TestCase):
    """If PR-029 is ever amended, this tool's whole shape changes. These fail loudly rather
    than letting it keep refusing on a ratio that no longer reads that way."""

    def record(self):
        p = ROOT / ".harness" / "precedents" / "PR-029.json"
        if not p.is_file():
            self.skipTest("PR-029 is not in this registry")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_clause_6_still_forbids_zero(self):
        self.assertIn("never as zero", self.record()["ratio"])

    def test_clause_6_still_requires_two_registries(self):
        self.assertIn("only once two domain registries exist", self.record()["ratio"])

    def test_the_record_still_carries_no_dicta(self):
        """Empty dicta is why every clause binds. If dicta appear, the clauses this tool leans
        on may have become persuasive rather than binding."""
        self.assertEqual(self.record().get("dicta"), [])

    def test_clause_5_still_defines_no_threshold(self):
        ratio = self.record()["ratio"]
        self.assertIn("trends toward negligible", ratio)
        # If a number ever appears alongside that phrase, NO THRESHOLD RATIFIED stops being
        # true and this tool must be revisited.
        tail = ratio[ratio.find("trends toward negligible"):][:400]
        self.assertFalse(any(ch.isdigit() for ch in tail.replace("(5)", "").replace("(6)", "")),
                         "a number now appears in clause 5; the threshold may be ratified")


if __name__ == "__main__":
    unittest.main()
