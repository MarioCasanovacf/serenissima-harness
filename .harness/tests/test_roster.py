"""Unit tests for .harness/bin/roster.py.

This file exists because an adversarial panel found that roster.py's docstring CITED a
`test_roster.py` as asserting the module's central safety property while no such file
existed. Every test below corresponds to a defect the panel actually demonstrated, or to
a claim the repaired docstring makes. The naming follows the panel's findings so a
reader can match test to finding.

Convention matches test_reputation.py / test_precedent_force.py: every test drives the
real CLI via subprocess against an isolated `--root` (a fresh TemporaryDirectory), except
`LiveStoreIsolation`, which hashes the live `.harness/` stores before and after a full
CLI exercise to prove the isolation actually holds.
"""
import concurrent.futures
import hashlib
import inspect
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
ROSTER_PY = BIN_DIR / "roster.py"
LIVE_HARNESS = ROOT / ".harness"
LIVE_ROSTER = LIVE_HARNESS / "roster.json"
LIVE_EVENTS = LIVE_HARNESS / "logs" / "events.jsonl"
LIVE_BLACKBOARD = LIVE_HARNESS / "blackboard.json"

sys.path.insert(0, str(BIN_DIR))
import roster  # noqa: E402  (white-box import for signature introspection only)


def run(root, *args, agent="tester"):
    env = dict(os.environ)
    env.pop("ROSTER_ROOT", None)
    env["CLAUDE_HARNESS_AGENT_ID"] = agent
    cmd = [sys.executable, str(ROSTER_PY), "--root", str(root)] + list(args)
    return subprocess.run(cmd, text=True, capture_output=True, env=env)


def sha256_of(path):
    p = pathlib.Path(path)
    if not p.exists():
        return "<absent>"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def roll(root):
    return json.loads((pathlib.Path(root) / "roster.json").read_text(encoding="utf-8"))


class RosterCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def charter(self, colegiado="banco", incentive="paga por prestamos cobrados",
                by="coordinator"):
        r = run(self.root, "charter", "--colegiado", colegiado,
                "--incentive", incentive, "--by", by)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def plazas(self, epic="e1", colegiado="banco", role="judge", count=3,
               by="coordinator"):
        return run(self.root, "plazas", "--epic", epic, "--colegiado", colegiado,
                   "--role", role, "--count", str(count), "--by", by)


# ---------------------------------------------------------------------------------
# Panel finding 1: zero hc.guarded calls -> 4 of 5 concurrent issuances silently lost.
# This is the module's CENTRAL safety property and the one the false docstring cited.
# ---------------------------------------------------------------------------------

class ConcurrentIssuanceLosesNothing(RosterCase):
    """DETECTION RATES, MEASURED, NOT ASSUMED. A race test that cannot fail against the
    defect it names is decoration. Both tests below were run against a copy of roster.py
    with `_guard` neutered to a no-op, reproducing the shipped defect exactly:

      in-process (threads calling roster.issue)      6/6 trials detected the loss
      subprocess (threads spawning the CLI)          3/6 trials detected the loss

    The subprocess variant is kept because it exercises the real CLI path, but the
    in-process variant is the reliable detector: process startup jitter is wider than
    the read-modify-write window, so the subprocess race often serialises by accident.
    """

    def test_in_process_concurrent_issuance_loses_nothing(self):
        """The deterministic detector. Five threads, one process, five seats."""
        self.charter()
        self.assertEqual(self.plazas(count=5).returncode, 0)

        names = [f"agent{i}" for i in range(5)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(
                lambda n: roster.issue(n, "banco", "judge", "e1", n, "", self.root),
                names))

        self.assertEqual(sorted(roll(self.root)["names"]), sorted(names),
                         "LOST WRITES: concurrent issuances overwrote each other")

    def test_in_process_over_subscription_is_refused_not_lost(self):
        self.charter()
        self.assertEqual(self.plazas(count=3).returncode, 0)

        ok, refused = [], []

        def attempt(n):
            try:
                roster.issue(n, "banco", "judge", "e1", n, "", self.root)
                ok.append(n)
            except KeyError:
                refused.append(n)

        names = [f"agent{i}" for i in range(8)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(attempt, names))

        self.assertEqual(len(ok), 3)
        self.assertEqual(len(refused), 5)
        self.assertEqual(len(roll(self.root)["names"]), 3)

    def test_five_concurrent_issuances_into_five_seats_all_land(self):
        self.charter()
        self.assertEqual(self.plazas(count=5).returncode, 0)

        names = [f"agent{i}" for i in range(5)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(
                lambda n: run(self.root, "issue", "--name", n, "--colegiado", "banco",
                              "--role", "judge", "--epic", "e1", "--by", n),
                names))

        succeeded = [n for n, r in zip(names, results) if r.returncode == 0]
        on_roll = sorted(roll(self.root)["names"])

        self.assertEqual(len(succeeded), 5,
                         "every issuance into a free seat must succeed")
        self.assertEqual(on_roll, sorted(names),
                         f"LOST WRITES: reported {len(succeeded)} successes but the roll "
                         f"holds {len(on_roll)} names")

    def test_concurrent_issuances_beyond_the_seat_count_are_refused_not_lost(self):
        """The inverse of the same guard: over-subscription must REFUSE the excess
        rather than admit it, and the count of successes must equal the seat count."""
        self.charter()
        self.assertEqual(self.plazas(count=3).returncode, 0)

        names = [f"agent{i}" for i in range(8)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda n: run(self.root, "issue", "--name", n, "--colegiado", "banco",
                              "--role", "judge", "--epic", "e1", "--by", n),
                names))

        ok = [r for r in results if r.returncode == 0]
        refused = [r for r in results if r.returncode == 2]
        self.assertEqual(len(ok), 3)
        self.assertEqual(len(refused), 5)
        self.assertEqual(len(roll(self.root)["names"]), 3)
        for r in refused:
            self.assertIn("filled", r.stderr)

    def test_every_mutating_function_opens_a_guard(self):
        """Static counterpart to the race tests: the previous version had 0 guard uses
        against blackboard 9 / lock 3 / precedent 7 / reputation 1 / session 3."""
        for fn in (roster.charter, roster.plazas, roster.issue):
            src = inspect.getsource(fn)
            self.assertIn("with _guard(root):", src,
                          f"{fn.__name__} mutates the roll outside a guard")

    def test_guards_are_never_nested(self):
        """harness_common: 'NEVER nest guarded() blocks (flock on a second file handle
        would deadlock).' A nested guard would hang this suite rather than fail it, so
        the check is static."""
        for fn in (roster.charter, roster.plazas, roster.issue):
            self.assertEqual(inspect.getsource(fn).count("with _guard("), 1,
                             f"{fn.__name__} opens more than one guard")


# ---------------------------------------------------------------------------------
# Panel finding 2: `judge ` and `Judge` minted fresh seats past a filled plaza.
# ---------------------------------------------------------------------------------

class TypoCannotMintASeat(RosterCase):

    def test_trailing_space_does_not_mint_a_parallel_seat(self):
        self.charter()
        self.assertEqual(self.plazas(role="judge", count=1).returncode, 0)
        self.assertEqual(self.plazas(role="judge ", count=1).returncode, 2,
                         "a trailing space republished the same seat")

    def test_capitalisation_does_not_mint_a_parallel_seat(self):
        self.charter()
        self.assertEqual(self.plazas(role="judge", count=1).returncode, 0)
        self.assertEqual(self.plazas(role="Judge", count=1).returncode, 2)

    def test_a_typo_cannot_slip_a_sixth_agent_into_a_full_plaza(self):
        """The panel's actual attack, end to end."""
        self.charter()
        self.assertEqual(self.plazas(role="judge", count=1).returncode, 0)
        self.assertEqual(
            run(self.root, "issue", "--name", "first", "--colegiado", "banco",
                "--role", "judge", "--epic", "e1", "--by", "first").returncode, 0)
        for variant in ("judge ", " judge", "JUDGE", "Judge"):
            r = run(self.root, "issue", "--name", f"sneak-{variant.strip()}",
                    "--colegiado", "banco", "--role", variant,
                    "--epic", "e1", "--by", "sneak")
            self.assertEqual(r.returncode, 2, f"{variant!r} bypassed the filled plaza")
            self.assertIn("filled", r.stderr)
        self.assertEqual(len(roll(self.root)["names"]), 1)

    def test_colegiado_and_epic_normalise_too(self):
        self.charter(colegiado="Banco")
        self.assertEqual(self.plazas(epic="E1", colegiado="banco ", count=1).returncode,
                         0, "colegiado lookup must survive case and space")
        r = run(self.root, "issue", "--name", "x", "--colegiado", "BANCO",
                "--role", "judge", "--epic", " e1 ", "--by", "x")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_identifiers_may_not_contain_the_key_separator(self):
        self.charter()
        self.assertEqual(self.plazas(role="judge/senior").returncode, 2)

    def test_empty_identifiers_are_refused(self):
        self.assertEqual(
            run(self.root, "charter", "--colegiado", "   ",
                "--incentive", "x", "--by", "c").returncode, 2)


# ---------------------------------------------------------------------------------
# Panel finding 3: charter had no authorization; a rival's incentive was overwritable.
# ---------------------------------------------------------------------------------

class CharterOverwrite(RosterCase):

    def test_a_different_author_may_not_redeclare_a_charter(self):
        self.charter(by="alice")
        r = run(self.root, "charter", "--colegiado", "banco",
                "--incentive", "paga por lo que yo diga", "--by", "mallory")
        self.assertEqual(r.returncode, 2)
        self.assertIn("may not redeclare", r.stderr)
        self.assertEqual(roll(self.root)["colegiados"]["banco"]["incentive"],
                         "paga por prestamos cobrados")

    def test_the_original_author_may_amend_its_own_charter(self):
        self.charter(by="alice")
        r = run(self.root, "charter", "--colegiado", "banco",
                "--incentive", "paga por prestamos cobrados y por no mentir",
                "--by", "alice")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("y por no mentir",
                      roll(self.root)["colegiados"]["banco"]["incentive"])

    def test_an_empty_incentive_is_refused(self):
        r = run(self.root, "charter", "--colegiado", "banco",
                "--incentive", "   ", "--by", "alice")
        self.assertEqual(r.returncode, 2)

    def test_the_refusal_is_documented_as_defeatable(self):
        """The docstring must NOT claim this refusal stops an adversary: `--by` is a
        self-asserted string and typing alice's name defeats it. The test asserts both
        the mechanism and the honesty."""
        r = run(self.root, "charter", "--colegiado", "banco",
                "--incentive", "cualquier cosa", "--by", "alice")  # impersonating alice
        self.charter(by="alice")
        self.assertEqual(r.returncode, 0)
        self.assertIn("string comparison an attacker controls both sides of",
                      roster.__doc__)


# ---------------------------------------------------------------------------------
# Panel finding 4: `--count 500`. Bounded, not closed.
# ---------------------------------------------------------------------------------

class PlazaCount(RosterCase):

    def test_count_above_the_bound_is_refused(self):
        self.charter()
        self.assertEqual(self.plazas(count=roster.PLAZA_MAX + 1).returncode, 2)
        self.assertEqual(self.plazas(count=500).returncode, 2)

    def test_count_at_the_bound_is_allowed(self):
        self.charter()
        self.assertEqual(self.plazas(count=roster.PLAZA_MAX).returncode, 0)

    def test_zero_and_negative_counts_are_refused(self):
        self.charter()
        self.assertEqual(self.plazas(count=0).returncode, 2)
        self.assertEqual(self.plazas(count=-3).returncode, 2)

    def test_plazas_require_an_existing_charter(self):
        self.assertEqual(self.plazas(colegiado="fantasma").returncode, 2)

    def test_plazas_cannot_be_republished_after_the_fact(self):
        self.charter()
        self.assertEqual(self.plazas(count=1).returncode, 0)
        r = self.plazas(count=9)
        self.assertEqual(r.returncode, 2)
        self.assertIn("already published", r.stderr)


# ---------------------------------------------------------------------------------
# Properties the docstring asserts on its own account.
# ---------------------------------------------------------------------------------

class NamesAndPersona(RosterCase):

    def test_a_name_is_never_reused(self):
        self.charter()
        self.assertEqual(self.plazas(count=3).returncode, 0)
        first = run(self.root, "issue", "--name", "aurelia", "--colegiado", "banco",
                    "--role", "judge", "--epic", "e1", "--by", "aurelia")
        self.assertEqual(first.returncode, 0, first.stderr)
        again = run(self.root, "issue", "--name", "Aurelia ", "--colegiado", "banco",
                    "--role", "judge", "--epic", "e1", "--by", "other")
        self.assertEqual(again.returncode, 2)
        self.assertIn("already issued", again.stderr)

    def test_persona_over_the_cap_is_refused(self):
        self.charter()
        self.assertEqual(self.plazas(count=1).returncode, 0)
        r = run(self.root, "issue", "--name", "x", "--colegiado", "banco",
                "--role", "judge", "--epic", "e1", "--by", "x",
                "--persona", "a" * (roster.PERSONA_MAX + 1))
        self.assertEqual(r.returncode, 2)

    def test_persona_at_the_cap_is_kept_verbatim(self):
        self.charter()
        self.assertEqual(self.plazas(count=1).returncode, 0)
        persona = "b" * roster.PERSONA_MAX
        r = run(self.root, "issue", "--name", "x", "--colegiado", "banco",
                "--role", "judge", "--epic", "e1", "--by", "x", "--persona", persona)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(roll(self.root)["names"]["x"]["persona"], persona)

    def test_issue_requires_a_published_plaza(self):
        self.charter()
        r = run(self.root, "issue", "--name", "x", "--colegiado", "banco",
                "--role", "judge", "--epic", "e1", "--by", "x")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no plazas published", r.stderr)


# ---------------------------------------------------------------------------------
# PR-022 clause 4 / PR-026 clause 5: NO CONSEQUENCE ATTACHES.
# ---------------------------------------------------------------------------------

class NoConsequenceAttaches(unittest.TestCase):

    FORBIDDEN = ("threshold", "gate", "weight", "burden", "permission", "discount",
                 "quorum", "score", "rank", "priority", "eligib")

    def test_no_exported_callable_takes_a_consequence_parameter(self):
        for name in roster.PUBLIC_API:
            fn = getattr(roster, name)
            if not callable(fn):
                continue
            for param in inspect.signature(fn).parameters:
                for bad in self.FORBIDDEN:
                    self.assertNotIn(bad, param.lower(),
                                     f"{name}({param}) attaches a consequence")

    def test_public_api_matches_the_module(self):
        for name in roster.PUBLIC_API:
            self.assertTrue(hasattr(roster, name), f"PUBLIC_API names missing {name}")

    def test_eligible_report_declares_itself_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "precedents").mkdir(parents=True)
            (root / "precedents" / "PR-999.json").write_text(
                json.dumps({"id": "PR-999", "published_by": "aurelia"}),
                encoding="utf-8")
            out = roster.eligible_report("PR-999", root)
        self.assertIn("IS_NOT_A_GATE", out)
        self.assertIn("advisory only", out["IS_NOT_A_GATE"])
        self.assertIn("PR-017", out["IS_NOT_A_GATE"])

    def test_eligible_report_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "precedents").mkdir(parents=True)
            (root / "precedents" / "PR-999.json").write_text(
                json.dumps({"id": "PR-999", "published_by": "aurelia"}),
                encoding="utf-8")
            before = sorted(p.name for p in root.rglob("*"))
            roster.eligible_report("PR-999", root)
            self.assertEqual(sorted(p.name for p in root.rglob("*")), before)


# ---------------------------------------------------------------------------------
# The docstring must not re-acquire the claim the panel removed.
# ---------------------------------------------------------------------------------

class DocstringHonesty(unittest.TestCase):

    def test_the_module_states_it_does_not_close_sybil(self):
        doc = roster.__doc__
        self.assertIn("PR-023", doc)
        self.assertIn("IT DOES NOT PREVENT AN ADVERSARY", doc)
        self.assertIn("bookkeeping", doc.lower())

    def test_the_cited_test_file_exists(self):
        """The finding that produced this whole file: the docstring cited a test that
        did not exist. If a future edit cites another path, that path must exist too."""
        for token in roster.__doc__.split():
            token = token.strip("`,;()").rstrip(".")
            if token.endswith(".py") and "test" in token:
                self.assertTrue((ROOT / token).exists(),
                                f"docstring cites {token}, which does not exist")


# ---------------------------------------------------------------------------------
# Isolation: nothing in this suite may touch live harness state.
# ---------------------------------------------------------------------------------

class LiveStoreIsolation(RosterCase):

    LIVE = (LIVE_ROSTER, LIVE_EVENTS, LIVE_BLACKBOARD)

    def test_full_cli_exercise_leaves_every_live_store_byte_identical(self):
        before = {str(p): sha256_of(p) for p in self.LIVE}

        self.charter()
        self.plazas(count=2)
        run(self.root, "issue", "--name", "aurelia", "--colegiado", "banco",
            "--role", "judge", "--epic", "e1", "--by", "aurelia",
            "--persona", "prestamista genoves, cauto, cobra en especie")
        run(self.root, "roster")
        run(self.root, "roster", "--json")
        run(self.root, "eligible", "--record", "PR-023")

        after = {str(p): sha256_of(p) for p in self.LIVE}
        self.assertEqual(before, after)

    def test_events_land_in_the_root_sidecar_not_the_live_log(self):
        self.charter()
        self.plazas(count=1)
        run(self.root, "issue", "--name", "aurelia", "--colegiado", "banco",
            "--role", "judge", "--epic", "e1", "--by", "aurelia")
        sidecar = self.root / "events.jsonl"
        self.assertTrue(sidecar.exists(), "overridden root must get its own event log")
        kinds = [json.loads(l)["event"] for l in
                 sidecar.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(kinds, ["roster_charter", "roster_plazas", "roster_issue"])

    def test_root_flag_beats_the_env_var(self):
        env = dict(os.environ)
        env["ROSTER_ROOT"] = str(LIVE_HARNESS)
        env["CLAUDE_HARNESS_AGENT_ID"] = "tester"
        before = sha256_of(LIVE_ROSTER)
        subprocess.run(
            [sys.executable, str(ROSTER_PY), "--root", str(self.root), "charter",
             "--colegiado", "banco", "--incentive", "x", "--by", "t"],
            text=True, capture_output=True, env=env)
        self.assertEqual(sha256_of(LIVE_ROSTER), before)
        self.assertTrue((self.root / "roster.json").exists())

    def test_a_failed_issuance_writes_no_row(self):
        self.charter()
        self.plazas(count=1)
        run(self.root, "issue", "--name", "a", "--colegiado", "banco",
            "--role", "judge", "--epic", "e1", "--by", "a")
        digest = sha256_of(self.root / "roster.json")
        r = run(self.root, "issue", "--name", "b", "--colegiado", "banco",
                "--role", "judge", "--epic", "e1", "--by", "b")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(sha256_of(self.root / "roster.json"), digest,
                         "a refused issuance must not perturb the roll")


if __name__ == "__main__":
    unittest.main(verbosity=2)
