"""T-402 / D4a: dispose of a novel case by CITATION instead of by legislation.

THE GAP THIS FILLS, which is not the one the task title suggests. `distinguishes` already
existed as a RELATION on `publish`. So the layer could already distinguish -- but only by
PUBLISHING A RECORD. Every novel case therefore cost an act of legislation: a permanent,
immutable tier-N record needing its own confirmation under PR-015. The verb here disposes of
a case by naming the nearest record and the material difference, signs that, and creates NO
record. The registry does not grow. That is what makes the two paths countable against each
other, which is the whole of D4a.

WHAT THESE TESTS ARE MOSTLY ABOUT:

  - The cheap path must not be the LAX path. Every refusal `publish` applies to a
    `distinguishes` relation is applied here too, plus one more. If distinguishing were
    easier to do badly than legislating, the ratio would measure corner-cutting.
  - The verb must WRITE NO RECORD. Pinned by comparing the registry byte-for-byte.
  - The ratio must not claim a denominator it does not have. `disposition-ratio` reports the
    share of DISPOSITIONS MADE and says, in the output, that the share of CASES ARISING is a
    different and unmeasured quantity. A test asserts the disclaimer is present and names the
    specific trap: inferring cases from dispositions would make the denominator a function of
    the numerator and the ratio would read 1.0 forever.
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
SHORT = "es distinto"


class Distinguishing(Enrolled):
    """A warrant fixture (from T-400) plus a small precedent registry in the same root.

    The two live together on purpose: `distinguish` reads the registry AND signs an act, so a
    fixture that separated them would not exercise the path that ships.
    """

    def setUp(self):
        super().setUp()
        self.reg = self.root / "precedents"
        self.reg.mkdir(parents=True, exist_ok=True)
        self.write_record("PR-001", scope=["aplica solo a nombres con warrant vigente"])

    def write_record(self, pr_id, scope=None, status="active", title="registro de prueba"):
        rec = {
            "id": pr_id, "title": title, "subject": "prueba", "status": status,
            "authority_tier": 2, "ratio": "una regla que obliga",
            "scope_conditions": scope if scope is not None else [],
            "validity_conditions": ["mientras el gate siga abierto"],
            "revisit_trigger": "al vencer el warrant",
            "relations": [], "cites": [], "dicta": [],
            "interpretive_code_version": "v1", "declared_width": "narrow",
            "operation": "determination", "issuing_task": "T-000",
            "tier_evidence": ["T-000"], "confirmation_status": "unconfirmed",
            "sources": ["prueba"],
        }
        (self.reg / (pr_id + ".json")).write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return rec

    def registry_bytes(self):
        return {p.name: p.read_bytes() for p in sorted(self.reg.glob("PR-*.json"))}

    def cli(self, *argv):
        # --root is the PRECEDENTS directory (SDR-13); the harness root is its parent and is
        # found from there. Getting this backwards is what broke the first implementation, so
        # the test passes the same two paths the real caller does rather than papering over it.
        return subprocess.run([sys.executable, str(CLI)] + list(argv) +
                              ["--root", str(self.reg)], capture_output=True, text=True)

    def intent(self, name="orso", task="T-1"):
        return attest.declare_intent(self.root, name, self.keys[name], "distinguish", task,
                                     "dispongo del caso citando PR-001")

    def distinguish(self, *, case="T-9", nearest="PR-001", facts=FACTS, name="orso",
                    task="T-1"):
        return self.cli("distinguish", "--case", case, "--nearest", nearest,
                        "--facts", facts, "--by", name,
                        "--key", str(self.keys[name]), "--task", task)


class TheDisposal(Distinguishing):

    def test_a_distinguish_succeeds_and_signs_an_act(self):
        self.intent()
        r = self.distinguish()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NO RECORD PUBLISHED", r.stdout)
        acts = [a for a in attest.chain(self.root, "orso")
                if a.get("kind") == precedent.DISTINGUISH_KIND]
        self.assertEqual(len(acts), 1)
        body = acts[0]["body"]
        self.assertEqual(body["nearest"], "PR-001")
        self.assertEqual(body["case"], "T-9")
        self.assertEqual(body["material_difference"], FACTS)

    def test_it_writes_no_precedent_record(self):
        """The property the whole task rests on, checked byte-for-byte rather than by count.

        A count would pass if the verb rewrote an existing record in place.
        """
        before = self.registry_bytes()
        self.intent()
        self.assertEqual(self.distinguish().returncode, 0)
        self.assertEqual(self.registry_bytes(), before)

    def test_the_act_says_it_binds_nobody(self):
        self.intent()
        self.distinguish()
        act = [a for a in attest.chain(self.root, "orso")
               if a.get("kind") == precedent.DISTINGUISH_KIND][0]
        body = act["body"]
        self.assertIn("NO PRECEDENT RECORD WAS CREATED", body["DISPOSES_WITHOUT_LEGISLATING"])
        self.assertIn("binds nobody", body["DISPOSES_WITHOUT_LEGISLATING"])
        self.assertIn("not citable as authority", body["DISPOSES_WITHOUT_LEGISLATING"])
        # And it must point at the right verb for the other case, or the cheap path becomes
        # the default way to make law without saying so.
        self.assertIn("publish", body["IF_THIS_SHOULD_BIND"])
        self.assertIn("PR-015", body["IF_THIS_SHOULD_BIND"])

    def test_it_requires_a_declared_intent_first(self):
        """D3a and D4a compose: `distinguish` is already a privileged kind, and disposing of
        a case for everyone afterwards is exactly the act whose deliberation should predate
        it."""
        r = self.distinguish()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no open intent", r.stderr)

    def test_an_unissued_name_cannot_distinguish(self):
        r = self.cli("distinguish", "--case", "T-9", "--nearest", "PR-001",
                     "--facts", FACTS, "--by", "fantasma",
                     "--key", str(self.keys["orso"]), "--task", "T-1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("can sign nothing", r.stderr)

    def test_facts_can_come_from_a_file(self):
        # P-021: prose belongs in files, not in flags.
        p = pathlib.Path(self._tmp.name) / "facts.txt"
        p.write_text(FACTS, encoding="utf-8")
        self.intent()
        r = self.cli("distinguish", "--case", "T-9", "--nearest", "PR-001",
                     "--facts-file", str(p), "--by", "orso",
                     "--key", str(self.keys["orso"]), "--task", "T-1")
        self.assertEqual(r.returncode, 0, r.stderr)


class TheCheapPathIsNotTheLaxPath(Distinguishing):
    """Every refusal `publish` applies to a distinguishes relation is applied here, plus one.

    If distinguishing were easier to do BADLY than legislating, the ratio D4a asks for would
    be measuring corner-cutting rather than economy, and the number would look better the
    worse the work got.
    """

    def test_a_missing_target_is_refused(self):
        self.intent()
        r = self.distinguish(nearest="PR-999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not in this registry", r.stderr)
        self.assertIn("publish", r.stderr, "the refusal must name the alternative")

    def test_a_non_active_target_is_refused(self):
        self.write_record("PR-002", scope=["algo"], status="overruled")
        self.intent()
        r = self.distinguish(nearest="PR-002")
        self.assertEqual(r.returncode, 1)
        self.assertIn("dead law", r.stderr)

    def test_a_target_with_empty_scope_conditions_is_refused(self):
        """The same rule publish applies: with no stated scope, there is nothing for the facts
        to fall outside of."""
        self.write_record("PR-003", scope=[])
        self.intent()
        r = self.distinguish(nearest="PR-003")
        self.assertEqual(r.returncode, 1)
        self.assertIn("scope_conditions are empty", r.stderr)
        self.assertIn("cheap path is not the lax one", r.stderr)

    def test_empty_facts_are_refused(self):
        self.intent()
        r = self.distinguish(facts="   ")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SDR-17.7", r.stderr)

    def test_a_too_short_material_difference_is_refused(self):
        """THE ONE RULE STRICTER THAN publish, and the reason is specific: a published record
        carries a ratio, scope conditions and confirmation behind it. A distinguish act
        carries NOTHING but this sentence. It is the only record of the reasoning, so it has
        to be reviewable on its own."""
        self.intent()
        r = self.distinguish(facts=SHORT)
        self.assertEqual(r.returncode, 1)
        self.assertIn("under 12 words is not", r.stderr)
        self.assertIn("no ratio behind it", r.stderr)

    def test_a_refusal_writes_no_act_and_no_record(self):
        before = self.registry_bytes()
        self.intent()
        self.distinguish(facts=SHORT)
        self.assertEqual(self.registry_bytes(), before)
        self.assertEqual([a for a in attest.chain(self.root, "orso")
                          if a.get("kind") == precedent.DISTINGUISH_KIND], [])
        # and the intent is NOT consumed, so the operator can retry after fixing the facts
        self.assertEqual(len(attest.open_intents(self.root, "orso")), 1)

    def test_every_refusal_is_enumerable_from_one_function(self):
        """The refusals live in _distinguish_refusals so this test can enumerate them rather
        than trusting that the CLI path covers each one."""
        rec = {"status": "active", "scope_conditions": ["x"], "title": "t"}
        self.assertIsNone(precedent._distinguish_refusals(rec, FACTS, "PR-001"))
        self.assertIn("not in this registry",
                      precedent._distinguish_refusals(None, FACTS, "PR-001"))
        self.assertIn("dead law", precedent._distinguish_refusals(
            dict(rec, status="voided"), FACTS, "PR-001"))
        self.assertIn("scope_conditions are empty", precedent._distinguish_refusals(
            dict(rec, scope_conditions=[]), FACTS, "PR-001"))
        self.assertIn("SDR-17.7", precedent._distinguish_refusals(rec, "", "PR-001"))
        self.assertIn("12 words", precedent._distinguish_refusals(rec, SHORT, "PR-001"))


class TheRatio(Distinguishing):

    def test_the_split_counts_both_paths(self):
        self.intent()
        self.distinguish()
        out = precedent.disposition_counts(self.reg, self.root)
        self.assertEqual(out["by_citation_raw"], 1)
        self.assertEqual(out["by_legislation_raw"], 1)      # PR-001, active
        self.assertEqual(out["dispositions_raw"], 2)
        self.assertAlmostEqual(out["citation_share_of_dispositions"], 0.5)

    def test_only_active_records_count_as_legislation(self):
        self.write_record("PR-004", scope=["x"], status="overruled")
        out = precedent.disposition_counts(self.reg, self.root)
        self.assertEqual(out["by_legislation_raw"], 1,
                         "dead law is not a live disposition")

    def test_every_count_is_reported_raw_and_distinct(self):
        out = precedent.disposition_counts(self.reg, self.root)
        for stem in ("by_citation", "by_legislation", "dispositions"):
            self.assertIn(stem + "_raw", out)
            self.assertIn(stem + "_distinct", out)

    def test_no_denominator_is_claimed(self):
        """The honest half, and the half the task explicitly asked for."""
        out = precedent.disposition_counts(self.reg, self.root)
        note = out["NO_DENOMINATOR_RATIFIED"]
        self.assertIn("DISPOSITIONS MADE", note)
        self.assertIn("NOVEL CASES ARISING", note)
        self.assertIn("no register of cases PRESENTED", note)
        # It must also name the specific wrong way to fix it, or someone will fix it that way.
        self.assertIn("function of the numerator", note)
        self.assertIn("1.0 forever", note)

    def test_no_threshold_is_claimed_either(self):
        out = precedent.disposition_counts(self.reg, self.root)
        self.assertIn("NO THRESHOLD RATIFIED", out["WHAT_THE_SPLIT_MEANS"])

    def test_a_zero_disposition_registry_reports_none_not_zero(self):
        """A share of 0/0 must not print as 0.0%. That reads as "the citation path is failing"
        when the truth is "nothing has happened yet"."""
        for p in self.reg.glob("PR-*.json"):
            p.write_text(json.dumps({"id": p.stem, "status": "overruled",
                                     "scope_conditions": []}) + "\n", encoding="utf-8")
        out = precedent.disposition_counts(self.reg, self.root)
        self.assertEqual(out["dispositions_raw"], 0)
        self.assertIsNone(out["citation_share_of_dispositions"])
        r = self.cli("disposition-ratio")
        self.assertIn("sin disposiciones", r.stdout)

    def test_the_ratio_renders_and_prints_its_own_disclaimer(self):
        self.intent()
        self.distinguish()
        r = self.cli("disposition-ratio")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NO DENOMINATOR RATIFIED", r.stdout)
        self.assertIn("50.0%", r.stdout)

    def test_json_output_carries_the_same_disclaimers(self):
        r = self.cli("disposition-ratio", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIn("NO_DENOMINATOR_RATIFIED", out)
        self.assertIn("COUNTS_ARE_REPORTED_TWICE", out)


class TheEventTypeQuestion(unittest.TestCase):
    """T-402 cautioned that PR-022 clause 3 fixes the event types at exactly six, so a new
    event type might not be available. CHECKED, and the caution rests on a conflation.

    PR-022 clause 3's six are REPUTATION event types -- rule authorship, load-bearing
    citations received, consolidations achieved, proper overrulings issued and sustained,
    verification verdicts upheld, adjudications not reversed. They are credit-earning
    categories. Log event kinds are a different register entirely, and the log has always
    carried more than six.
    """

    def test_pr022_clause_3_is_about_reputation_not_logging(self):
        rec = json.loads((ROOT / ".harness" / "precedents" / "PR-022.json")
                         .read_text(encoding="utf-8"))
        ratio = rec["ratio"]
        clause = ratio[ratio.find("(3)"):ratio.find("(4)")]
        self.assertIn("exactly six", clause)
        # The six named are credit categories, not log kinds. If a future edit makes this
        # clause name log kinds, this test fails and the caution becomes real again.
        for token in ("rule authorship", "citations received", "verdicts upheld"):
            self.assertIn(token, clause)
        self.assertNotIn("event kind", clause)

    def test_the_live_log_already_carries_more_than_six_kinds(self):
        """The decisive evidence: if clause 3 governed log kinds, this harness would already
        be in violation, and it is not."""
        log = ROOT / ".harness" / "logs" / "events.jsonl"
        if not log.is_file():
            self.skipTest("no live event log in this checkout")
        kinds = set()
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                kinds.add(json.loads(line).get("event"))
            except json.JSONDecodeError:
                continue
        self.assertGreater(len(kinds), 6,
                           "if the log carried six or fewer kinds this argument would need "
                           "different evidence")


if __name__ == "__main__":
    unittest.main()
