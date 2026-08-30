"""test_deliberate.py -- unit test suite for Deliberation Protocol (.harness/bin/deliberate.py).

Verifies:
  1. Proposal creation, dossier ID allocation (D-001, D-002...), required field validation.
  2. 3-sponsor quorum floor (nuisance proposal prevention before scheduling).
  3. Pre-deliberation straw poll (Bayesian prior recording).
  4. Deterministic seeded speaker shuffle (order-effect neutralization and reproducibility).
  5. Post-deliberation ranked voting and Condorcet conclusion via Schulze/Copeland engine.
  6. CLI subcommands and JSON outputs.
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import deliberate  # noqa: E402
import harness_common as hc  # noqa: E402

CLI = ROOT / ".harness" / "bin" / "deliberate.py"


class DeliberationProtocolTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hroot = pathlib.Path(self._tmp.name)
        self.delib_dir = self.hroot / "deliberations"
        self.delib_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(args) + ["--harness-root", str(self.hroot)],
            capture_output=True, text=True
        )

    def test_propose_creates_dossier_and_enforces_fields(self):
        # Missing title refused
        r = self.run_cli("propose", "--title", "   ", "--evidence", "T-100", "--task", "T-100", "--proposer", "agent-1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("title must be non-empty", r.stderr)

        # Missing evidence refused
        r = self.run_cli("propose", "--title", "Prop A", "--task", "T-100", "--proposer", "agent-1")
        self.assertNotEqual(r.returncode, 0)

        # Successful propose
        r = self.run_cli("propose", "--title", "Upgrade Substrate", "--evidence", "T-100",
                         "--evidence", "PR-015", "--task", "T-100", "--proposer", "agent-1",
                         "--alternatives", "opt1", "--alternatives", "opt2", "--alternatives", "opt3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("proposed deliberation dossier D-001", r.stdout)

        dossier_file = self.delib_dir / "D-001.json"
        self.assertTrue(dossier_file.exists())
        data = json.loads(dossier_file.read_text(encoding="utf-8"))
        self.assertEqual(data["id"], "D-001")
        self.assertEqual(data["title"], "Upgrade Substrate")
        self.assertEqual(data["proposer"], "agent-1")
        self.assertEqual(data["sponsors"], ["agent-1"])
        self.assertEqual(data["status"], "proposed")
        self.assertEqual(data["evidence"], ["T-100", "PR-015"])

    def test_three_sponsor_quorum_floor_enforcement(self):
        # Propose D-001 (1 sponsor: agent-1)
        self.run_cli("propose", "--title", "Policy X", "--evidence", "T-100", "--task", "T-100", "--proposer", "agent-1")

        # Attempt to schedule deliberation with only 1 sponsor -> Refused by 3-sponsor quorum floor!
        r_sched1 = self.run_cli("schedule", "D-001", "--speakers", "agent-1,agent-2")
        self.assertEqual(r_sched1.returncode, 1)
        self.assertIn("3-sponsor quorum floor not met", r_sched1.stderr)

        # Add 2nd sponsor
        r_spon2 = self.run_cli("sponsor", "D-001", "--by", "agent-2")
        self.assertEqual(r_spon2.returncode, 0, r_spon2.stderr)

        # Still 2 sponsors -> Refused
        r_sched2 = self.run_cli("schedule", "D-001", "--speakers", "agent-1,agent-2")
        self.assertEqual(r_sched2.returncode, 1)
        self.assertIn("3-sponsor quorum floor not met", r_sched2.stderr)

        # Add 3rd sponsor -> Now passes the 3-sponsor floor!
        r_spon3 = self.run_cli("sponsor", "D-001", "--by", "agent-3")
        self.assertEqual(r_spon3.returncode, 0, r_spon3.stderr)

        # Scheduling now succeeds!
        r_sched3 = self.run_cli("schedule", "D-001", "--speakers", "agent-1,agent-2,agent-3")
        self.assertEqual(r_sched3.returncode, 0, r_sched3.stderr)
        self.assertIn("DELIBERATION SPEAKER SCHEDULE", r_sched3.stdout)

    def test_deterministic_seeded_speaker_shuffle(self):
        speakers = ["agent-alpha", "agent-beta", "agent-gamma", "agent-delta", "agent-epsilon"]
        seed1 = "fixed-seed-42"
        seed2 = "another-seed-99"

        order1_a = deliberate.compute_deterministic_speaker_order(speakers, seed1)
        order1_b = deliberate.compute_deterministic_speaker_order(speakers, seed1)
        order2 = deliberate.compute_deterministic_speaker_order(speakers, seed2)

        # Reproducibility check: identical seed yields identical order
        self.assertEqual(order1_a, order1_b)
        self.assertEqual(sorted(order1_a), sorted(speakers))

        # Different seed yields different order
        self.assertNotEqual(order1_a, order2)

    def test_full_deliberation_lifecycle_and_condorcet_conclusion(self):
        # 1. Propose
        r = self.run_cli("propose", "--title", "Choose Optimizer", "--evidence", "benchmarks.csv",
                         "--task", "T-200", "--proposer", "worker-1",
                         "--alternatives", "AdamW", "--alternatives", "SGD", "--alternatives", "Lion")
        self.assertEqual(r.returncode, 0)

        # 2. Record Priors (Straw Poll)
        self.run_cli("prior", "D-001", "--voter", "worker-1", "--ranking", "AdamW,Lion,SGD")
        self.run_cli("prior", "D-001", "--voter", "worker-2", "--ranking", "Lion,AdamW,SGD")
        self.run_cli("prior", "D-001", "--voter", "worker-3", "--ranking", "SGD,AdamW,Lion")

        # 3. Sponsor to reach quorum
        self.run_cli("sponsor", "D-001", "--by", "worker-2")
        self.run_cli("sponsor", "D-001", "--by", "worker-3")

        # 4. Schedule Speakers
        r_sched = self.run_cli("schedule", "D-001", "--json")
        self.assertEqual(r_sched.returncode, 0)
        sched_data = json.loads(r_sched.stdout)
        self.assertEqual(sched_data["status"], "deliberating")
        self.assertEqual(len(sched_data["speaker_order"]), 3)

        # 4b. Discussion: T-418 guard 1 requires at least one non-empty round
        # per alternative before a deliberation may conclude.
        for alt in ("AdamW", "SGD", "Lion"):
            rd = self.run_cli("discuss", "D-001", "--by", "worker-1", "--re", alt,
                              "--text", "case for/against %s on the benchmarks" % alt)
            self.assertEqual(rd.returncode, 0, rd.stderr)

        # 5. Vote Post-Deliberation
        self.run_cli("vote", "D-001", "--voter", "worker-1", "--ranking", "AdamW,Lion,SGD")
        self.run_cli("vote", "D-001", "--voter", "worker-2", "--ranking", "AdamW,Lion,SGD")
        self.run_cli("vote", "D-001", "--voter", "worker-3", "--ranking", "Lion,AdamW,SGD")

        # 6. Conclude Deliberation with Condorcet Tally
        r_conc = self.run_cli("conclude", "D-001", "--method", "schulze", "--json")
        self.assertEqual(r_conc.returncode, 0)
        res = json.loads(r_conc.stdout)
        self.assertEqual(res["status"], "concluded")
        self.assertEqual(res["tally_result"]["winner"], "AdamW")
        self.assertEqual(res["tally_result"]["condorcet_winner"], "AdamW")

        # 7. Show Dossier
        r_show = self.run_cli("show", "D-001")
        self.assertEqual(r_show.returncode, 0)
        self.assertIn("DELIBERATION DOSSIER: D-001 [CONCLUDED]", r_show.stdout)
        self.assertIn("Winner:    AdamW", r_show.stdout)



class TheClerkConstraintIsMechanical(unittest.TestCase):
    """T-417. The W-002 charter says clerks "NO legisla, NO vota, NO tiene stake" and D-001
    proved nothing enforced it: a clerk-named proposer, three clerk sponsors and three clerk
    ballots concluded a constitutional docket in 71 seconds. These tests pin the two rules
    that make the charter mechanical, and the bootstrap posture that keeps every pre-roster
    harness (including every other test class in this file) working unchanged.
    """

    CHARTER = ("integridad del proceso; NO legisla, NO vota, NO tiene stake "
               "(AgentCity clerk constraint)")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hroot = pathlib.Path(self._tmp.name)
        (self.hroot / "deliberations").mkdir(parents=True)
        roster = {
            "schema_version": 1,
            "colegiados": {
                "fedatario": {"incentive": self.CHARTER},
                "registro": {"incentive": "registros confirmados que sobreviven"},
                "revision": {"incentive": "refutaciones que se sostienen"},
            },
            "names": {
                "fed-relator": {"colegiado": "fedatario", "role": "relator"},
                "fed-codificador": {"colegiado": "fedatario", "role": "codificador"},
                "registro-a": {"colegiado": "registro", "role": "author"},
                "revision-doctrina": {"colegiado": "revision", "role": "verifier"},
                "revision-ataque": {"colegiado": "revision", "role": "verifier"},
                "revision-mecanismo": {"colegiado": "revision", "role": "verifier"},
            },
        }
        (self.hroot / "roster.json").write_text(json.dumps(roster), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(args) + ["--harness-root", str(self.hroot)],
            capture_output=True, text=True)

    def propose_ok(self):
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "registro-a",
                         "--alternatives", "adopt", "--alternatives", "reject")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.split()[3].rstrip(":")

    def test_a_clerk_proposer_is_refused_naming_the_charter(self):
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "fed-relator")
        self.assertEqual(r.returncode, 1)
        self.assertIn("clerk seat", r.stderr)
        self.assertIn("NO legisla, NO vota", r.stderr)

    def test_a_clerk_sponsor_is_refused(self):
        dossier = self.propose_ok()
        r = self.run_cli("sponsor", dossier, "--by", "fed-codificador")
        self.assertEqual(r.returncode, 1)
        self.assertIn("clerk seat", r.stderr)

    def test_a_clerk_prior_and_ballot_are_refused(self):
        dossier = self.propose_ok()
        for verb in ("prior", "vote"):
            with self.subTest(verb=verb):
                r = self.run_cli(verb, dossier, "--voter", "fed-relator",
                                 "--ranking", "adopt,reject")
                self.assertEqual(r.returncode, 1)
                self.assertIn("clerk seat", r.stderr)

    def test_an_unissued_name_is_refused(self):
        """D-001's actual voters. `clerk-relator` was never issued: the real clerk seats are
        `fed-*`. A name with no seat has no standing, whatever it calls itself."""
        r = self.run_cli("propose", "--title", "Revision of PR-022", "--evidence", "PR-060",
                         "--task", "T-416", "--proposer", "clerk-relator")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unissued name", r.stderr)

    def test_the_D001_replay_is_refused_at_its_first_input(self):
        """The regression the task demands: D-001's opening move, verbatim, against the
        guarded module. It must die at the proposer, before a dossier exists."""
        r = self.run_cli("propose",
                         "--title",
                         "Revision of PR-022 for operational reputation consequences",
                         "--evidence", "PR-060", "--task", "T-416",
                         "--proposer", "clerk-relator")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(list((self.hroot / "deliberations").iterdir()), [])

    def test_NEGATIVE_CONTROL_issued_non_clerk_names_run_the_whole_lifecycle(self):
        """Without this, every fix above could be "refuse everyone", which is a gate that
        closed the assembly instead of guarding it."""
        dossier = self.propose_ok()
        for by in ("revision-doctrina", "revision-ataque"):
            r = self.run_cli("sponsor", dossier, "--by", by)
            self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_cli("prior", dossier, "--voter", "revision-mecanismo",
                         "--ranking", "adopt,reject")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_NEGATIVE_CONTROL_a_rosterless_root_keeps_bootstrap_behavior(self):
        """The no-flag-day posture, same as warrant.py: no roster, no gate. Every other
        test class in this file runs in exactly this state."""
        bare = pathlib.Path(self._tmp.name) / "bare"
        (bare / "deliberations").mkdir(parents=True)
        r = subprocess.run(
            [sys.executable, str(CLI), "propose", "--title", "t", "--evidence", "T-1",
             "--task", "T-1", "--proposer", "anybody", "--harness-root", str(bare)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_college_is_a_clerk_by_its_charter_not_by_its_name(self):
        """Rename the college and keep the charter: still refused. The rule keys on the
        declared constraint, so a future clerk college under another name is caught the day
        it is declared."""
        roster = json.loads((self.hroot / "roster.json").read_text(encoding="utf-8"))
        roster["colegiados"]["notariado"] = {"incentive": self.CHARTER}
        roster["names"]["not-1"] = {"colegiado": "notariado", "role": "x"}
        (self.hroot / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "not-1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("clerk seat", r.stderr)


class AnInconsistentRosterFailsClosed(TheClerkConstraintIsMechanical):
    """T-417, round-2 regression (verifier rejection replayed verbatim). The first cut
    resolved a missing colegiado to charter="", the clerk markers never matched, and an
    orphan seat was waved through with NO refusal at all: with colegiados["fedatario"]
    deleted and names["fed-relator"] unchanged, `sponsor --by fed-relator` exited 0.
    An inconsistent roster now gets the same posture as an unreadable one: refuse rather
    than guess. Inherits the intact-roster fixture (and the parent's tests, which re-run
    here as the A/B control: same roster minus the mutation, opposite outcome).
    """

    def mutate_roster(self, fn):
        roster = json.loads((self.hroot / "roster.json").read_text(encoding="utf-8"))
        fn(roster)
        (self.hroot / "roster.json").write_text(json.dumps(roster), encoding="utf-8")

    def test_the_verifier_repro_sponsor_by_orphan_colegiado_is_refused(self):
        dossier = self.propose_ok()
        self.mutate_roster(lambda r: r["colegiados"].pop("fedatario"))
        r = self.run_cli("sponsor", dossier, "--by", "fed-relator")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("roster inconsistent", r.stderr)
        self.assertIn("fedatario", r.stderr)

    def test_the_verifier_repro_propose_by_orphan_colegiado_is_refused(self):
        self.mutate_roster(lambda r: r["colegiados"].pop("registro"))
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "registro-a")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("roster inconsistent", r.stderr)

    def test_prior_and_vote_by_orphan_colegiado_are_refused(self):
        dossier = self.propose_ok()
        for by in ("revision-doctrina", "revision-ataque", "revision-mecanismo"):
            r = self.run_cli("sponsor", dossier, "--by", by)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.mutate_roster(lambda r: r["colegiados"].pop("revision"))
        r = self.run_cli("prior", dossier, "--voter", "revision-doctrina",
                         "--ranking", "adopt,reject")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("roster inconsistent", r.stderr)
        r = self.run_cli("vote", dossier, "--voter", "revision-doctrina",
                         "--ranking", "adopt,reject")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("roster inconsistent", r.stderr)

    def test_a_colegiado_with_no_charter_text_is_refused(self):
        """The sibling hole: an EXISTING colegiado whose incentive is empty or absent
        also resolves to an uncheckable charter -- same fail-closed posture."""
        self.mutate_roster(lambda r: r["colegiados"]["registro"].update({"incentive": ""}))
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "registro-a")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no charter text", r.stderr)
        self.mutate_roster(lambda r: r["colegiados"]["registro"].pop("incentive"))
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "registro-a")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no charter text", r.stderr)


class DeliberationIntegrityGuards(unittest.TestCase):
    """T-418. D-001 concluded in 71 seconds with no recorded discussion, four
    ballots identical to four identical priors, and stamps three days in the
    future. Three guards answer those three defects; each carries its negative
    control. These run in a rosterless root (no eligibility gate), so they test
    the integrity guards in isolation from T-417's clerk gate."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hroot = pathlib.Path(self._tmp.name)
        (self.hroot / "deliberations").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(args) + ["--harness-root", str(self.hroot)],
            capture_output=True, text=True)

    def convene(self, alternatives=("A", "B")):
        """Propose -> 3 sponsors -> priors -> schedule. Returns dossier id."""
        alt_args = []
        for a in alternatives:
            alt_args += ["--alternatives", a]
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "w1", *alt_args)
        self.assertEqual(r.returncode, 0, r.stderr)
        did = r.stdout.split()[3].rstrip(":")
        for by in ("w2", "w3"):
            self.assertEqual(self.run_cli("sponsor", did, "--by", by).returncode, 0)
        self.run_cli("prior", did, "--voter", "w1", "--ranking", ",".join(alternatives))
        self.assertEqual(self.run_cli("schedule", did, "--speakers", "w1,w2,w3").returncode, 0)
        return did

    def dossier(self, did):
        return json.loads((self.hroot / "deliberations" / (did + ".json")).read_text())

    def write_dossier(self, did, data):
        (self.hroot / "deliberations" / (did + ".json")).write_text(
            json.dumps(data), encoding="utf-8")

    # -- Guard 1: discussion evidence --------------------------------------

    def test_conclude_refused_when_an_alternative_has_no_discussion(self):
        did = self.convene(("A", "B"))
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "case for A")
        # B is never discussed.
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no discussion recorded", r.stderr)
        self.assertIn("'B'", r.stderr)

    def test_conclude_succeeds_once_every_alternative_is_discussed(self):
        did = self.convene(("A", "B"))
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "for A")
        self.run_cli("discuss", did, "--by", "w2", "--re", "B", "--text", "for B")
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_empty_discussion_text_is_refused_at_write(self):
        did = self.convene(("A", "B"))
        r = self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "   ")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("non-empty", r.stderr)

    def test_hand_edited_empty_round_does_not_satisfy_the_guard(self):
        """Re-validated at conclude: an empty-text round injected straight into
        the JSON counts for nothing."""
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        data["discussion"] = [{"by": "w1", "re": "A", "text": "", "at": hc.now_iso()},
                              {"by": "w1", "re": "B", "text": "  ", "at": hc.now_iso()}]
        self.write_dossier(did, data)
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no discussion recorded", r.stderr)

    def test_discussion_round_pointed_at_a_nonexistent_alternative_is_refused(self):
        did = self.convene(("A", "B"))
        r = self.run_cli("discuss", did, "--by", "w1", "--re", "Z", "--text", "for Z")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("not an alternative", r.stderr)

    def test_emptying_alternatives_after_voting_does_not_skip_discussion(self):
        """T-419 round-2 escape: hand-editing alternatives to [] made
        undiscussed_alternatives vacuously empty and conclude passed a
        zero-discussion docket. The requirement is now derived from the ballots
        too, so emptying the field removes nothing that must be discussed."""
        did = self.convene(("A", "B"))
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        data = self.dossier(did)
        data["alternatives"] = []          # the exact attack
        self.write_dossier(did, data)
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no discussion recorded", r.stderr)

    def test_deleting_the_alternatives_key_after_voting_is_caught(self):
        did = self.convene(("A", "B"))
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        data = self.dossier(did)
        del data["alternatives"]           # key-deletion variant
        self.write_dossier(did, data)
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no discussion recorded", r.stderr)

    def test_conclude_on_no_candidates_at_all_is_refused_as_malformed(self):
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        # No alternatives, no candidate named in any ballot OR prior: nothing
        # to decide among at all.
        data["alternatives"] = []
        data["priors"] = {}
        data["final_ballots"] = {"w1": {"ranking": [], "weight": 1.0, "voted_at": hc.now_iso()}}
        self.write_dossier(did, data)
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no alternatives to decide among", r.stderr)

    def test_emptying_alternatives_still_concludes_if_every_candidate_was_discussed(self):
        """The fix must not break the honest path: with the field emptied but
        every ballot candidate genuinely discussed, conclude still succeeds."""
        did = self.convene(("A", "B"))
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "for A")
        self.run_cli("discuss", did, "--by", "w2", "--re", "B", "--text", "for B")
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        data = self.dossier(did)
        data["alternatives"] = []
        self.write_dossier(did, data)
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_discuss_before_convening_is_refused(self):
        r = self.run_cli("propose", "--title", "t", "--evidence", "T-1", "--task", "T-1",
                         "--proposer", "w1", "--alternatives", "A", "--alternatives", "B")
        did = r.stdout.split()[3].rstrip(":")
        r = self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "early")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("convened", r.stderr)

    # -- Guard 2: NO-DELIBERATION-OBSERVED flag ----------------------------

    def test_flag_fires_when_every_ballot_equals_its_prior(self):
        did = self.convene(("A", "B"))
        self.run_cli("prior", did, "--voter", "w1", "--ranking", "A,B")
        self.run_cli("prior", did, "--voter", "w2", "--ranking", "A,B")
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "for A")
        self.run_cli("discuss", did, "--by", "w2", "--re", "B", "--text", "for B")
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        self.run_cli("vote", did, "--voter", "w2", "--ranking", "A,B")
        r = self.run_cli("conclude", did, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["deliberation_flag"], "NO-DELIBERATION-OBSERVED")

    def test_flag_is_a_flag_not_a_block(self):
        """The conclusion still succeeds and the tally is present -- unanimity
        can be honest."""
        did = self.convene(("A", "B"))
        self.run_cli("prior", did, "--voter", "w1", "--ranking", "A,B")
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "for A")
        self.run_cli("discuss", did, "--by", "w1", "--re", "B", "--text", "for B")
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        r = self.run_cli("conclude", did, "--json")
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "concluded")
        self.assertIsNotNone(data["tally_result"])

    def test_flag_does_not_fire_when_a_ballot_differs_from_its_prior(self):
        did = self.convene(("A", "B"))
        self.run_cli("prior", did, "--voter", "w1", "--ranking", "A,B")
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "for A")
        self.run_cli("discuss", did, "--by", "w1", "--re", "B", "--text", "for B")
        # ballot flips relative to the prior: the discussion moved someone.
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "B,A")
        r = self.run_cli("conclude", did, "--json")
        self.assertEqual(json.loads(r.stdout)["deliberation_flag"], "deliberation-observed")

    def test_flag_does_not_fire_when_a_voter_arrived_without_a_prior(self):
        did = self.convene(("A", "B"))
        # w1 has a prior (from convene) but w2 votes with none.
        self.run_cli("discuss", did, "--by", "w1", "--re", "A", "--text", "for A")
        self.run_cli("discuss", did, "--by", "w2", "--re", "B", "--text", "for B")
        self.run_cli("vote", did, "--voter", "w1", "--ranking", "A,B")
        self.run_cli("vote", did, "--voter", "w2", "--ranking", "A,B")
        r = self.run_cli("conclude", did, "--json")
        self.assertEqual(json.loads(r.stdout)["deliberation_flag"], "deliberation-observed")

    # -- Guard 3: future-stamp refusal -------------------------------------

    def test_future_dated_stamp_refuses_every_write_verb(self):
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        future = (hc.now_utc() + dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["created_at"] = future
        self.write_dossier(did, data)
        for verb, extra in (
            ("sponsor", ["--by", "w4"]),
            ("prior", ["--voter", "w5", "--ranking", "A,B"]),
            ("discuss", ["--by", "w1", "--re", "A", "--text", "x"]),
            ("vote", ["--voter", "w1", "--ranking", "A,B"]),
            ("conclude", []),
        ):
            r = self.run_cli(verb, did, *extra)
            self.assertEqual(r.returncode, 1, "%s should refuse: %s" % (verb, r.stdout))
            self.assertIn("future-dated stamp", r.stderr)

    def test_future_stamp_buried_deep_in_the_dossier_is_caught(self):
        """The scan is exhaustive, not a fixed key list: a future stamp on a
        nested ballot is caught as surely as one on created_at."""
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        future = (hc.now_utc() + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["final_ballots"] = {"w1": {"ranking": ["A", "B"], "weight": 1.0,
                                        "voted_at": future}}
        self.write_dossier(did, data)
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("future-dated stamp", r.stderr)
        self.assertIn("final_ballots", r.stderr)

    def test_future_stamp_smuggled_as_a_dict_key_is_caught(self):
        """T-418 verifier finding, closed: a future ISO string used as a KEY,
        not a value, was slipping the scan. No legitimate write emits a stamp
        as a key, so scanning keys only ever closes forgery."""
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        future = (hc.now_utc() + dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data[future] = "smuggled audit note"
        self.write_dossier(did, data)
        r = self.run_cli("sponsor", did, "--by", "w4")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("future-dated stamp", r.stderr)

    def test_reads_still_work_on_a_future_dated_dossier(self):
        """A tampered dossier must stay readable -- show is the audit path."""
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        data["created_at"] = (hc.now_utc() + dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write_dossier(did, data)
        r = self.run_cli("show", did)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_stamp_within_skew_is_allowed(self):
        """A stamp a minute ahead (clock jitter) is not 'from the future'."""
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        data["created_at"] = (hc.now_utc() + dt.timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write_dossier(did, data)
        r = self.run_cli("sponsor", did, "--by", "w4")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unparseable_stamp_fails_closed(self):
        did = self.convene(("A", "B"))
        data = self.dossier(did)
        data["created_at"] = "2026-13-99T99:99:99Z"  # matches the shape, cannot be ordered
        self.write_dossier(did, data)
        r = self.run_cli("sponsor", did, "--by", "w4")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("future-dated stamp", r.stderr)


class TheD001DefectCannotRecur(unittest.TestCase):
    """The three guards, composed: replay D-001's shape end to end under the
    live roster and the integrity guards together, and show it can no longer
    conclude. This is the regression fixture RAT-01 promised."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hroot = pathlib.Path(self._tmp.name)
        (self.hroot / "deliberations").mkdir(parents=True)
        # Real roster copied from the live one, so clerk names are refused too.
        live = ROOT / ".harness" / "roster.json"
        (self.hroot / "roster.json").write_text(live.read_text(encoding="utf-8"),
                                                encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(args) + ["--harness-root", str(self.hroot)],
            capture_output=True, text=True)

    def test_a_clerk_proposer_never_even_opens_the_dossier(self):
        r = self.run_cli("propose", "--title", "Phase B", "--evidence", "C-001",
                         "--task", "T-1", "--proposer", "fed-relator")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("clerk seat", r.stderr)
        self.assertFalse((self.hroot / "deliberations" / "D-001.json").exists())

    def test_a_non_clerk_docket_still_cannot_skip_discussion(self):
        r = self.run_cli("propose", "--title", "Phase B", "--evidence", "C-001",
                         "--task", "T-1", "--proposer", "registro-a",
                         "--alternatives", "adopt", "--alternatives", "reject")
        did = r.stdout.split()[3].rstrip(":")
        for by in ("revision-doctrina", "revision-ataque"):
            self.run_cli("sponsor", did, "--by", by)
        self.run_cli("schedule", did, "--speakers", "registro-a,revision-doctrina,revision-ataque")
        self.run_cli("vote", did, "--voter", "registro-a", "--ranking", "adopt,reject")
        r = self.run_cli("conclude", did)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no discussion recorded", r.stderr)


if __name__ == "__main__":
    unittest.main()
