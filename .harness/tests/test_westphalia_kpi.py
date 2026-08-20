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
import importlib.util
import json
import pathlib
import re
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


def as_published(out):
    """The report as a CONSUMER sees it, not as Python holds it.

    THE GUARD WALKS THIS AND NOT THE LIVE OBJECT, and that is the whole of the first repair.
    The first version of the walker recursed into `dict` and `list` only, so a figure wrapped
    in a one-element TUPLE was invisible to it -- while `json.dumps` serialized that tuple as
    a JSON array and published the number anyway. A verifier demonstrated it with the exact
    magnitude of the original attack sitting in real `--json` output.

    Round-tripping through JSON first collapses every container the CLI can actually emit into
    dict / list / number / string / bool / null. There is no third case to forget, because the
    published form is by definition what json.dumps produces.
    """
    return json.loads(json.dumps(out))


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def numeric_leaves(value, path="$"):
    """Every number the published report carries, with the path it sits at.

    Booleans are excluded: `True` is an int in Python and a flag is not a measurement.

    A STRING THAT IS ENTIRELY A NUMBER COUNTS AS A NUMBER, and that is the third bypass a
    verifier closed. `out["reconciliation_cost_hours"] = str(...)` was invisible to a walker
    that checked `isinstance(value, (int, float))`, while the figure sat in `--json` output as
    plain readable text. What a reader sees is a number; the type it was stored under is not
    the reader's problem.

    A string that merely CONTAINS a number is still exempt -- `operator_baseline` legitimately
    says "3 months" -- and that limit is stated on the guard class.
    """
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield path, value
    elif isinstance(value, str):
        text = value.strip()
        if text and NUMBER.fullmatch(text):
            yield path, float(text) if "." in text else int(text)
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from numeric_leaves(v, "%s.%s" % (path, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from numeric_leaves(v, "%s[%d]" % (path, i))


def strings_in(value):
    """Every string leaf of the published report, so a number quoted inside prose can be told
    from a number the renderer invented."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


def expected_numbers(root):
    """The COMPLETE specification of what numbers this report may carry, and where.

    A path-to-value map, not a set of allowed values, and that is the second repair. The first
    version asked "is this number in the allowed set", which a verifier beat by fabricating a
    figure that landed on an allowed value by coincidence: `registries_distinct +
    measurements_distinct` is 3 under the fixture, 3 was in the set, and a key named
    `reconciliation_cost_hours` sailed through carrying a meaningless sum of two counts.

    Membership was the wrong question. The right one is PROVENANCE: every number must sit at a
    path this map names AND equal the value independently recounted for that path. A key the
    map does not name fails whatever its value, so a fabricated figure cannot buy its way in by
    matching some unrelated count.

    The map is exhaustive on purpose. A new numeric key in the report fails here until somebody
    adds it deliberately and justifies what it counts -- which is the review this guard exists
    to force.

    It does NOT call the module. A guard that asks the module what it counted agrees with it by
    construction. Two declared CONSTANTS are read, because a report that prints a threshold the
    record itself states is quoting, not measuring, and an AST test pins that short list.
    """
    root = pathlib.Path(root)
    registry_dirs = [d for d in sorted(root.iterdir()) if d.is_dir()] if root.is_dir() else []
    with_records = [d for d in registry_dirs if list(d.glob("PR-*.json"))]
    store = root / "kpi" / "westphalia"
    files = sorted(store.glob("*.json")) if store.is_dir() else []
    quarters = set()
    for f in files:
        try:
            quarters.add(json.loads(f.read_text(encoding="utf-8")).get("quarter"))
        except json.JSONDecodeError:
            pass

    expected = {
        "$.registries_raw": len(with_records),
        "$.registries_distinct": len({d.name for d in with_records}),
        "$.registries_required": kpi.REQUIRED_REGISTRIES,
        "$.measurements_raw": len(files),
        "$.measurements_distinct": len(quarters) if files else 0,
        "$.measurements_needed_for_revisit": kpi.MEASUREMENTS_NEEDED_FOR_REVISIT,
    }
    for i, d in enumerate(with_records):
        expected["$.registries[%d].records" % i] = len(list(d.glob("PR-*.json")))
    return expected


class TheOutputCannotCarryAFabricatedFigure(Fixture):
    """T-410. The four AST guards watch NAMES; this one watches the OUTPUT.

    THE ATTACK THAT MOTIVATED IT, run by the verifier revision-mecanismo on 2026-08-17 and
    demonstrated rather than asserted: inject `registries_distinct * 40 + measurements_raw *
    1200000` under a new key `projected_effort_estimate`, using variable names containing none
    of the substrings the AST guards watch for, and never touching the key `cost`. ALL 28 TESTS
    PASSED and the fabricated figure appeared in `--json`.

    THE FIRST REPAIR OF THIS CLASS WAS ITSELF BEATEN, twice, by a second verifier, and both
    holes are closed above rather than documented as limits:

      a figure inside a TUPLE, which the walker did not descend into while json.dumps published
      it anyway -- closed by walking the published form (`as_published`);

      a figure that landed on an allowed VALUE by coincidence -- closed by replacing the set of
      allowed values with an exhaustive path-to-value map, so an unknown key fails whatever it
      carries.

    THE RULE NOW: every number the report publishes must sit at a path the specification names
    and equal the value independently recounted for it. A count is defensible. A product, a
    weighted sum, or a figure under a key nobody justified is an estimate, and PR-029 clause 6
    forbids estimating this cost today.

    WHAT IS STILL NOT COVERED, said plainly rather than left to be discovered: PROSE.
    `operator_baseline` legitimately contains "3 months", so string leaves are outside the rule
    and a figure smuggled into a sentence would pass. Bounding that needs a ratified definition
    of what a cost-shaped sentence is, and there is none.
    """

    def setUp(self):
        super().setUp()
        # Cardinalities chosen so no product or sum of them collides with a legitimate count.
        # 7 records, 3 measurement files, 2 distinct quarters, 1 registry.
        self.add_registry("precedents", "PR-", 7)
        store = self.root / "kpi" / "westphalia"
        store.mkdir(parents=True)
        for i, quarter in enumerate(["2026Q1", "2026Q1", "2026Q2"]):
            (store / "m{}.json".format(i)).write_text(
                json.dumps({"quarter": quarter}) + "\n", encoding="utf-8")

    def published_numbers(self, out=None):
        return dict(numeric_leaves(as_published(out if out is not None
                                                else kpi.report(self.root))))

    def test_the_report_carries_exactly_the_numbers_the_specification_names(self):
        self.assertEqual(self.published_numbers(), expected_numbers(self.root))

    def test_a_fabricated_figure_is_caught_whatever_it_is_called(self):
        """NEGATIVE CONTROL. Without it the test above passes on a guard that checks nothing,
        which is precisely how the four AST guards passed the original attack."""
        out = kpi.report(self.root)
        out["projected_effort_estimate"] = (
            out["registries_distinct"] * 40 + out["measurements_raw"] * 1200000)
        self.assertNotEqual(self.published_numbers(out), expected_numbers(self.root))

    def test_a_figure_wrapped_in_a_tuple_is_caught(self):
        """The first bypass a verifier found. `json.dumps` publishes a tuple as an array, so
        a walker that skipped tuples skipped a number the CLI printed."""
        out = kpi.report(self.root)
        out["reconciliation_effort_estimate"] = (
            out["registries_distinct"] * 40 + out["measurements_raw"] * 1200000,)
        numbers = self.published_numbers(out)
        self.assertIn("$.reconciliation_effort_estimate[0]", numbers)
        self.assertNotEqual(numbers, expected_numbers(self.root))

    def test_a_figure_that_lands_on_a_legitimate_count_by_coincidence_is_caught(self):
        """The second bypass. `registries_distinct + measurements_distinct` is 3 here, and 3 is
        a real count elsewhere in this report -- which is exactly why membership in a set of
        allowed values was the wrong question."""
        out = kpi.report(self.root)
        out["reconciliation_cost_hours"] = (
            out["registries_distinct"] + out["measurements_distinct"])
        self.assertEqual(out["reconciliation_cost_hours"], 3)
        self.assertIn(3, expected_numbers(self.root).values())
        self.assertNotEqual(self.published_numbers(out), expected_numbers(self.root))

    def test_a_figure_buried_in_a_nested_structure_is_caught(self):
        out = kpi.report(self.root)
        out["instrumentation"] = dict(out["instrumentation"])
        out["instrumentation"]["modelled"] = {"hours": [{"q1": 640}]}
        self.assertIn("$.instrumentation.modelled.hours[0].q1", self.published_numbers(out))

    def test_a_legitimate_count_that_stops_matching_its_own_recount_is_caught(self):
        """The other direction: a key the specification names, carrying the wrong number.
        Without this the map could be satisfied by any report with the right SHAPE."""
        out = kpi.report(self.root)
        out["measurements_raw"] = out["measurements_raw"] + 1
        self.assertNotEqual(self.published_numbers(out), expected_numbers(self.root))

    def test_a_figure_stored_as_a_numeric_string_is_caught(self):
        """The third bypass. A reader sees a number; the type it was stored under is not the
        reader's problem, and `--json` prints it either way."""
        out = kpi.report(self.root)
        out["reconciliation_cost_hours"] = str(
            out["registries_distinct"] * 40 + out["measurements_raw"] * 1200000)
        numbers = self.published_numbers(out)
        self.assertEqual(numbers.get("$.reconciliation_cost_hours"), 3600040)
        self.assertNotEqual(numbers, expected_numbers(self.root))

    def test_prose_that_merely_contains_a_number_is_still_exempt(self):
        """NEGATIVE CONTROL for the rule above. `operator_baseline` says "3 months" and must
        stay outside the rule, or the guard fails every honest report."""
        out = kpi.report(self.root)
        self.assertIn("3 months", out["operator_baseline"])
        self.assertEqual(self.published_numbers(), expected_numbers(self.root))

    def test_the_text_mode_prints_no_number_the_report_does_not_carry(self):
        """The fourth bypass: a figure computed inside `_render` and printed only in TEXT mode
        never touches the report dict, so every guard that inspects the dict is blind to it --
        and text mode is what a human actually runs.

        Every number the renderer prints has to be traceable to the published report: either a
        numeric leaf, or text inside one of its strings (clause numbers, "3 months", record
        ids). A number in neither was invented by the renderer.
        """
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = as_published(kpi.report(self.root))
        from_values = {str(v) for _, v in numeric_leaves(out)}
        prose = " ".join(s for s in strings_in(out))
        unexplained = [n for n in NUMBER.findall(proc.stdout)
                       if n not in from_values and n not in prose]
        self.assertEqual(unexplained, [],
                         "text mode printed numbers that appear nowhere in the report")

    def test_a_flag_is_not_a_measurement(self):
        """Booleans are ints in Python. Counting them would either force `True` into the
        specification -- which admits every 1 -- or fail every report that has a flag."""
        self.assertEqual(list(numeric_leaves({"store_exists": True, "n": 7})), [("$.n", 7)])

    def test_the_specification_never_calls_the_module_it_checks(self):
        """GUARD-MENTION-C, sixth occurrence: parsed, not scanned. A recount that delegated to
        `kpi.domain_registries` would confirm the module against itself."""
        source = pathlib.Path(__file__).read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(source))
                  if isinstance(n, ast.FunctionDef) and n.name == "expected_numbers")
        called = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    called.add("%s.%s" % (node.func.value.id, node.func.attr))
        self.assertEqual({c for c in called if c.startswith("kpi.")}, set(),
                         "the specification calls the module it is supposed to check")
        constants = {n.attr for n in ast.walk(fn)
                     if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                     and n.value.id == "kpi"}
        self.assertEqual(constants, {"REQUIRED_REGISTRIES", "MEASUREMENTS_NEEDED_FOR_REVISIT"})

    def test_the_verifiers_attack_replayed_against_a_patched_MODULE_is_caught(self):
        """The reproduction, not a paraphrase of it.

        The tests above inject into the returned dict. This one patches the module the way the
        verifier did -- new key, variable names carrying none of the watched substrings, `cost`
        untouched -- imports the patched copy, and runs it. It asserts two things in order:
        that the four AST guards STILL pass on the patched module, which is the finding; and
        that the output guard catches what they miss.
        """
        patched = pathlib.Path(self._tmp.name) / "patched_kpi.py"
        source = CLI.read_text(encoding="utf-8")
        needle = "    if not enough:\n        out[\"WHY_NO_FIGURE\"]"
        self.assertIn(needle, source)
        injection = (
            "    span = out[\"registries_distinct\"]\n"
            "    weight = out[\"measurements_raw\"]\n"
            "    out[\"projected_effort_estimate\"] = span * 40 + weight * 1200000\n")
        patched.write_text(source.replace(needle, injection + needle, 1), encoding="utf-8")

        # The AST guards, replayed verbatim against the patched module: they pass.
        tree = ast.parse(patched.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                            and t.slice.value == "cost"):
                        self.assertIsInstance(node.value, ast.Constant)
                        self.assertIsNone(node.value.value)
            if isinstance(node, ast.BinOp):
                names = [n.id.lower() for n in ast.walk(node) if isinstance(n, ast.Name)]
                for bad in ("hour", "token", "cost"):
                    self.assertFalse(any(bad in n for n in names),
                                     "the injection was supposed to evade this guard")

        spec = importlib.util.spec_from_file_location("patched_kpi", patched)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out = module.report(self.root)
        self.assertIn("projected_effort_estimate", out)
        self.assertNotEqual(self.published_numbers(out), expected_numbers(self.root))


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
