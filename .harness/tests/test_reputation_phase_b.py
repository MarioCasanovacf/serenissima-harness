"""test_reputation_phase_b.py -- Unit tests and PoC for Phase B Reputation (PR-060/PR-061).

Verifies:
  1. Exponential Moving Average (EMA) half-life decay formula accuracy.
  2. Decayed component score computation (rules, citations, overrulings, verdicts).
  3. `rank` CLI command: ranks identities by operational score descending.
  4. `dispatch` CLI command: recommends task claim priority queue based on operational score.
  5. `audit-immunity` CLI command: asserts PR-060 constitutional split and D-17 non-staking hold.
  6. Proof of Concept: simulated multi-agent workload and dynamic decay over time.
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
REPUTATION_PY = BIN_DIR / "reputation.py"

sys.path.insert(0, str(BIN_DIR))
import reputation as rep  # noqa: E402


class EMADecayFormulaTests(unittest.TestCase):

    def test_zero_delta_yields_full_weight(self):
        now_dt = dt.datetime(2026, 8, 25, 0, 0, 0, tzinfo=dt.timezone.utc)
        event_ts = "2026-08-25T00:00:00Z"
        decay = rep._compute_ema_decay(event_ts, now_dt, half_life_days=30.0)
        self.assertAlmostEqual(decay, 1.0, places=4)

    def test_one_half_life_yields_half_weight(self):
        now_dt = dt.datetime(2026, 8, 25, 0, 0, 0, tzinfo=dt.timezone.utc)
        # 30 days prior
        event_ts = "2026-07-26T00:00:00Z"
        decay = rep._compute_ema_decay(event_ts, now_dt, half_life_days=30.0)
        self.assertAlmostEqual(decay, 0.5, places=2)

    def test_two_half_lives_yields_quarter_weight(self):
        now_dt = dt.datetime(2026, 8, 25, 0, 0, 0, tzinfo=dt.timezone.utc)
        # 60 days prior
        event_ts = "2026-06-26T00:00:00Z"
        decay = rep._compute_ema_decay(event_ts, now_dt, half_life_days=30.0)
        self.assertAlmostEqual(decay, 0.25, places=2)


class PhaseBCLICommandsTests(unittest.TestCase):

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(REPUTATION_PY)] + list(args),
            capture_output=True, text=True
        )

    def test_rank_subcommand_json(self):
        r = self.run_cli("rank", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["phase"], "B")
        self.assertEqual(data["authority"], "PR-061 / PR-060")
        self.assertTrue(len(data["rankings"]) > 0)
        # Check sorted descending
        scores = [item["total_score"] for item in data["rankings"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_dispatch_queue_priority(self):
        r = self.run_cli("dispatch", "--candidates", "worker-gemini,clerk-relator,coordinator-gemini",
                         "--tasks", "T-500,T-501", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["phase"], "B")
        self.assertIn("recommended_claim_order", data)
        self.assertEqual(len(data["recommended_claim_order"]), 3)
        self.assertEqual(data["constitutional_immunity"]["status"], "PASS")

    def test_audit_immunity_command(self):
        r = self.run_cli("audit-immunity", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertTrue(data["constitutional_invariants"]["PR-060_split_enforced"])
        self.assertTrue(data["constitutional_invariants"]["D-17_non_staking_no_asset_loss"])


class ProofOfConceptSimulationTests(unittest.TestCase):
    """PoC: Simulate dynamic ranking over time as older contributions decay."""

    def test_poc_dynamic_decay_shift(self):
        now_fresh = dt.datetime(2026, 8, 25, 0, 0, 0, tzinfo=dt.timezone.utc)
        now_future_90d = dt.datetime(2026, 11, 23, 0, 0, 0, tzinfo=dt.timezone.utc)

        root = rep.DEFAULT_ROOT
        precedents = rep.load_precedents(root)
        blackboard_tasks = rep.load_blackboard_tasks(root)
        reopened = rep.load_reopened_tasks(root)

        ident = "worker-build-4"
        score_fresh = rep._compute_phase_b_figures(ident, root, precedents, blackboard_tasks, reopened,
                                                   half_life_days=30.0, now_dt=now_fresh)
        score_90d = rep._compute_phase_b_figures(ident, root, precedents, blackboard_tasks, reopened,
                                                 half_life_days=30.0, now_dt=now_future_90d)

        # 90 days later (3 half-lives), score should have decayed to approximately 1/8th (12.5%) of fresh score
        self.assertTrue(score_fresh["total_score"] > 0)
        self.assertTrue(score_90d["total_score"] < score_fresh["total_score"])
        decay_ratio = score_90d["total_score"] / score_fresh["total_score"]
        self.assertAlmostEqual(decay_ratio, 0.125, delta=0.05)


if __name__ == "__main__":
    unittest.main()
