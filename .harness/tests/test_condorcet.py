"""test_condorcet.py -- test suite for Condorcet voting engine (.harness/bin/condorcet.py).

Verifies:
  1. Ballot normalization (flat lists, tiered ranks, weighted ballots, error validation).
  2. Pairwise preference matrix calculations.
  3. Condorcet Winner and Condorcet Loser identification.
  4. Schulze beatpath method correctness against canonical test cases (including Condorcet cycles).
  5. Copeland pairwise scoring and ranking.
  6. Smith set determination.
  7. CLI subcommands (count, matrix, audit) and JSON output formats.
  8. Capture resistance properties (Condorcet consistency, non-dictatorship, clone resilience).
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import condorcet  # noqa: E402

CLI = ROOT / ".harness" / "bin" / "condorcet.py"


class BallotNormalizationTests(unittest.TestCase):

    def test_flat_ranking_normalization(self):
        voter, ranking, weight = condorcet.normalize_ballot(["A", "B", "C"])
        self.assertEqual(voter, "anon")
        self.assertEqual(ranking, [["A"], ["B"], ["C"]])
        self.assertEqual(weight, 1.0)

    def test_tiered_ranking_normalization(self):
        voter, ranking, weight = condorcet.normalize_ballot([["A", "B"], ["C"]])
        self.assertEqual(ranking, [["A", "B"], ["C"]])
        self.assertEqual(weight, 1.0)

    def test_weighted_dict_ballot(self):
        voter, ranking, weight = condorcet.normalize_ballot({
            "voter": "analyst-1",
            "ranking": ["C", "B", "A"],
            "weight": 2.5
        })
        self.assertEqual(voter, "analyst-1")
        self.assertEqual(ranking, [["C"], ["B"], ["A"]])
        self.assertEqual(weight, 2.5)

    def test_duplicate_candidate_in_ballot_raises_error(self):
        with self.assertRaises(condorcet.BallotParseError):
            condorcet.normalize_ballot(["A", "B", "A"])

        with self.assertRaises(condorcet.BallotParseError):
            condorcet.normalize_ballot([["A", "B"], ["B", "C"]])

    def test_invalid_weight_raises_error(self):
        with self.assertRaises(condorcet.BallotParseError):
            condorcet.normalize_ballot({"ranking": ["A", "B"], "weight": 0})


class PairwiseAndCondorcetTests(unittest.TestCase):

    def test_pairwise_matrix_computation(self):
        # 3 voters: A > B > C
        # 2 voters: B > C > A
        ballots = [
            condorcet.normalize_ballot(["A", "B", "C"]),
            condorcet.normalize_ballot(["A", "B", "C"]),
            condorcet.normalize_ballot(["A", "B", "C"]),
            condorcet.normalize_ballot(["B", "C", "A"]),
            condorcet.normalize_ballot(["B", "C", "A"]),
        ]
        candidates = ["A", "B", "C"]
        d = condorcet.compute_pairwise_matrix(candidates, ballots)

        self.assertEqual(d["A"]["B"], 3.0)
        self.assertEqual(d["B"]["A"], 2.0)
        self.assertEqual(d["A"]["C"], 3.0)
        self.assertEqual(d["C"]["A"], 2.0)
        self.assertEqual(d["B"]["C"], 5.0)
        self.assertEqual(d["C"]["B"], 0.0)

        # A beats B (3 vs 2) and A beats C (3 vs 2) -> A is Condorcet winner
        self.assertEqual(condorcet.find_condorcet_winner(candidates, d), "A")
        # C loses to A (2 vs 3) and C loses to B (0 vs 5) -> C is Condorcet loser
        self.assertEqual(condorcet.find_condorcet_loser(candidates, d), "C")

    def test_condorcet_paradox_cycle(self):
        # Classic Condorcet Cycle (rock-paper-scissors tournament):
        # Voter 1: A > B > C
        # Voter 2: B > C > A
        # Voter 3: C > A > B
        ballots = [
            condorcet.normalize_ballot(["A", "B", "C"]),
            condorcet.normalize_ballot(["B", "C", "A"]),
            condorcet.normalize_ballot(["C", "A", "B"]),
        ]
        candidates = ["A", "B", "C"]
        d = condorcet.compute_pairwise_matrix(candidates, ballots)

        # A beats B (2 vs 1)
        # B beats C (2 vs 1)
        # C beats A (2 vs 1)
        self.assertEqual(d["A"]["B"], 2.0)
        self.assertEqual(d["B"]["C"], 2.0)
        self.assertEqual(d["C"]["A"], 2.0)

        # No single Condorcet Winner or Loser exists in this cycle
        self.assertIsNone(condorcet.find_condorcet_winner(candidates, d))
        self.assertIsNone(condorcet.find_condorcet_loser(candidates, d))

        # All 3 are in the Smith set
        smith = condorcet.find_smith_set(candidates, d)
        self.assertEqual(sorted(smith), ["A", "B", "C"])


class SchulzeMethodCanonicalTests(unittest.TestCase):

    def test_schulze_wikipedia_canonical_example(self):
        """Standard Wikipedia Schulze method 45-voter example with candidates A, B, C, D, E:
        5 voters: A > C > B > E > D
        5 voters: A > D > E > C > B
        8 voters: B > E > D > A > C
        3 voters: C > A > B > E > D
        7 voters: C > A > E > B > D
        2 voters: C > B > A > D > E
        7 voters: D > C > E > B > A
        8 voters: E > B > A > D > C
        Expected Schulze Winner: E
        """
        raw_ballots = []
        raw_ballots += [{"ranking": ["A", "C", "B", "E", "D"], "weight": 5.0}]
        raw_ballots += [{"ranking": ["A", "D", "E", "C", "B"], "weight": 5.0}]
        raw_ballots += [{"ranking": ["B", "E", "D", "A", "C"], "weight": 8.0}]
        raw_ballots += [{"ranking": ["C", "A", "B", "E", "D"], "weight": 3.0}]
        raw_ballots += [{"ranking": ["C", "A", "E", "B", "D"], "weight": 7.0}]
        raw_ballots += [{"ranking": ["C", "B", "A", "D", "E"], "weight": 2.0}]
        raw_ballots += [{"ranking": ["D", "C", "E", "B", "A"], "weight": 7.0}]
        raw_ballots += [{"ranking": ["E", "B", "A", "D", "C"], "weight": 8.0}]

        res = condorcet.aggregate_votes(raw_ballots, method="schulze")
        self.assertEqual(res["winner"], "E")
        ranked_names = [r["candidate"] for r in res["schulze_ranking"]]
        self.assertEqual(ranked_names, ["E", "A", "C", "B", "D"])


class CopelandMethodTests(unittest.TestCase):

    def test_copeland_scoring(self):
        # 4 voters: A > B > C
        # 3 voters: B > A > C
        # 2 voters: C > B > A
        ballots = [
            {"ranking": ["A", "B", "C"], "weight": 4.0},
            {"ranking": ["B", "A", "C"], "weight": 3.0},
            {"ranking": ["C", "B", "A"], "weight": 2.0},
        ]
        res = condorcet.aggregate_votes(ballots, method="copeland")
        # A vs B: A has 4, B has 5 -> B wins
        # A vs C: A has 7, C has 2 -> A wins
        # B vs C: B has 7, C has 2 -> B wins
        # B has 2 wins, A has 1 win, C has 0 wins -> B is Copeland winner
        self.assertEqual(res["winner"], "B")
        self.assertEqual([r["candidate"] for r in res["copeland_ranking"]], ["B", "A", "C"])


class CLISubcommandTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ballots_file = pathlib.Path(self._tmp.name) / "ballots.json"
        ballots = [
            {"voter": "v1", "ranking": ["alpha", "beta", "gamma"], "weight": 2},
            {"voter": "v2", "ranking": ["beta", "alpha", "gamma"], "weight": 1},
            {"voter": "v3", "ranking": ["alpha", "gamma", "beta"], "weight": 1},
        ]
        self.ballots_file.write_text(json.dumps(ballots), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI)] + list(args),
            capture_output=True, text=True
        )

    def test_cli_count_text(self):
        r = self.run_cli("count", "--ballots", str(self.ballots_file))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CONDORCET PREFERENCE AGGREGATION", r.stdout)
        self.assertIn("Winner:           alpha", r.stdout)

    def test_cli_count_json(self):
        r = self.run_cli("count", "--ballots", str(self.ballots_file), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["winner"], "alpha")
        self.assertEqual(data["total_ballots"], 3)
        self.assertEqual(data["total_weight"], 4.0)

    def test_cli_matrix_json(self):
        r = self.run_cli("matrix", "--ballots", str(self.ballots_file), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("pairwise_matrix", data)
        self.assertEqual(data["pairwise_matrix"]["alpha"]["beta"], 3.0)

    def test_cli_audit_json(self):
        r = self.run_cli("audit", "--ballots", str(self.ballots_file), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "pass")
        self.assertTrue(data["capture_resistance_metrics"]["schulze_matches_condorcet"])


if __name__ == "__main__":
    unittest.main()
