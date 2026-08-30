"""test_deliberate.py -- unit test suite for Deliberation Protocol (.harness/bin/deliberate.py).

Verifies:
  1. Proposal creation, dossier ID allocation (D-001, D-002...), required field validation.
  2. 3-sponsor quorum floor (nuisance proposal prevention before scheduling).
  3. Pre-deliberation straw poll (Bayesian prior recording).
  4. Deterministic seeded speaker shuffle (order-effect neutralization and reproducibility).
  5. Post-deliberation ranked voting and Condorcet conclusion via Schulze/Copeland engine.
  6. CLI subcommands and JSON outputs.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import deliberate  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
