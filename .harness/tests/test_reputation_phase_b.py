"""test_reputation_phase_b.py -- Phase B reputation: EMA decay + THE CONSTITUTIONAL GATE (T-420).

What Phase B is allowed to be (PR-060 split, PR-061 whose authority is
operator ruling RAT-01, not deliberation D-001):

  * consequences attach to OPERATIONAL parameters only (claim priority
    ordering); constitutional parameters (EMA decay rate, weights,
    thresholds) are the operator's alone;
  * under D-17 every agent shares one OS user, so the ONLY boundary that
    can mark an operator decision is the operator's private key held off
    this machine.

Therefore the gate: `dispatch` (the one consequence verb) refuses unless
`constitutional/reputation.json` carries a detached ssh signature that
verifies against the enrolled trust anchor in the "harness-constitutional"
namespace AND says activation on -- and its constitutional parameters come
from that signed payload ONLY.

Coverage:
  1. EMA half-life decay formula accuracy (kept from the first cut).
  2. The gate, attacked with real keys: absent file, unsigned file, wrong
     key, wrong namespace, tampered payload, activation off, un-enrolled
     trust. Each refuses with the failing condition named. The one
     authorized configuration runs, with parameters provably from the file.
  3. `--half-life-days` on dispatch is refused even when activated: a CLI
     knob that must match the file is a knob that leaks.
  4. `rank` stays a consequence-free report and labels its parameters
     ratified/NOT RATIFIED against the signed file.
  5. `audit-immunity` emits figures and NO verdict (currency.py precedent);
     the hardcoded-PASS dict it replaced is asserted gone.
  6. AST: no code path in reputation.py can write the constitutional file
     or sign anything -- the exhaustive map of write-capable calls has
     exactly one entry, the allowed_signers rebuild inside a system temp
     dir (warrant.py's own verification pattern).
  7. Zero writes across every Phase B verb, including the ACTIVATED
     consequence verb, against a snapshot-hashed fixture root.

Requires ssh-keygen (already a hard dependency of warrant.py's suite).
"""
import ast
import datetime as dt
import hashlib
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
import warrant as w  # noqa: E402


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(REPUTATION_PY)] + list(args),
        capture_output=True, text=True)


def keygen(path, comment="test"):
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", comment,
                    "-f", str(path), "-q"], check=True, capture_output=True)
    return pathlib.Path(str(path) + ".pub")


def sign(payload_path, key_path, namespace=rep.CONSTITUTIONAL_NAMESPACE):
    sig = pathlib.Path(str(payload_path) + ".sig")
    if sig.exists():
        sig.unlink()  # some ssh-keygen builds keep a stale .sig on re-sign
    r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key_path),
                        "-n", namespace, str(payload_path)],
                       text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return sig


def sha256_of(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


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


class GateFixture(unittest.TestCase):
    """A scratch harness root with a real enrolled trust anchor: an ed25519
    keypair generated per test class stands in for the operator's off-machine
    key, and a second keypair for the attacker."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.root = self.base / "harness"
        (self.root / "precedents").mkdir(parents=True)
        self.keys = self.base / "keys"
        self.keys.mkdir()
        self.operator_key = self.keys / "operator"
        self.operator_pub = keygen(self.operator_key, "operator@offmachine")
        self.mallory_key = self.keys / "mallory"
        self.mallory_pub = keygen(self.mallory_key, "mallory@onmachine")

    def enroll(self):
        td = self.root / "trust"
        td.mkdir(exist_ok=True)
        pub_line = self.operator_pub.read_text(encoding="utf-8").strip()
        (td / "root.pub").write_text(pub_line + "\n", encoding="utf-8")
        (td / "root.fingerprint").write_text(
            w.key_fingerprint(self.operator_pub) + "\n", encoding="utf-8")

    def write_constitutional(self, activation="on", half_life=45.0, weights=None,
                             namespace=rep.CONSTITUTIONAL_NAMESPACE):
        cdir = self.root / "constitutional"
        cdir.mkdir(exist_ok=True)
        path = cdir / "reputation.json"
        payload = {
            "schema_version": 1,
            "namespace": namespace,
            "subject": "reputation-phase-b",
            "authority": "PR-061 (RAT-01) / PR-060",
            "activation": activation,
            "ema_half_life_days": half_life,
            "weights": weights or {"rule_authorship": 1.0, "citations_received": 1.0,
                                   "consolidations": 2.0, "overrulings_sustained": 1.5,
                                   "verdicts_upheld": 1.0},
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def dispatch(self, *extra):
        return run_cli("dispatch", "--root", str(self.root),
                       "--candidates", "worker-a,worker-b", "--json", *extra)


class TheGateRefusesEveryUnauthorizedPath(GateFixture):

    def test_no_constitutional_file_refuses(self):
        self.enroll()
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("consequence verb", r.stderr)
        self.assertIn("NOT_PRESENT", r.stderr)
        # The refusal tells the operator exactly how to activate, and names
        # the constitutional namespace, never the warrant one.
        self.assertIn("harness-constitutional", r.stderr)
        self.assertNotIn("harness-warrant", r.stderr)

    def test_unsigned_file_refuses(self):
        self.enroll()
        self.write_constitutional()
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("UNSIGNED", r.stderr)

    def test_wrong_key_signature_refuses(self):
        """Mallory holds every on-machine secret (D-17) but not the operator's
        key: a signature by any other key fails verification."""
        self.enroll()
        path = self.write_constitutional()
        sign(path, self.mallory_key)
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("BAD_SIGNATURE", r.stderr)

    def test_wrong_namespace_signature_refuses(self):
        """The operator's own key signing in the WARRANT namespace does not
        authorize a constitutional file: namespaces are never shared, so a
        signed warrant payload can never double as a constitutional one."""
        self.enroll()
        path = self.write_constitutional()
        sign(path, self.operator_key, namespace="harness-warrant")
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("BAD_SIGNATURE", r.stderr)

    def test_tampered_payload_refuses(self):
        """Sign, then flip one constitutional parameter: the signature covers
        bytes, so the tamper invalidates it."""
        self.enroll()
        path = self.write_constitutional(half_life=45.0)
        sign(path, self.operator_key)
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("45.0", "1.0"), encoding="utf-8")
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("BAD_SIGNATURE", r.stderr)

    def test_activation_off_refuses(self):
        """A verified file whose activation is off is a ratification of
        parameters, not an authorization to run the consequence verb."""
        self.enroll()
        path = self.write_constitutional(activation="off")
        sign(path, self.operator_key)
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("VERIFIED_OFF", r.stderr)

    def test_unenrolled_trust_refuses_as_unverifiable(self):
        """Signed file, no trust anchor: a signature that cannot be checked
        authorizes nothing. This is the bootstrap posture -- the gate is
        closed, not open, before enrollment."""
        path = self.write_constitutional()
        sign(path, self.operator_key)
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("UNVERIFIABLE", r.stderr)

    def test_wrong_declared_namespace_in_payload_refuses(self):
        """A payload whose own namespace field lies is refused before any
        signature check."""
        self.enroll()
        path = self.write_constitutional(namespace="harness-warrant")
        sign(path, self.operator_key)
        r = self.dispatch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("WRONG_NAMESPACE", r.stderr)


class TheOneAuthorizedConfigurationRuns(GateFixture):

    def test_activated_dispatch_runs_with_parameters_from_the_file(self):
        self.enroll()
        path = self.write_constitutional(activation="on", half_life=45.0)
        sign(path, self.operator_key)
        r = self.dispatch()
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["constitutional_file"]["state"], "VERIFIED")
        self.assertEqual(data["parameters"]["source"], "signed constitutional file")
        # 45.0 is deliberately NOT the source default (30.0): the value in the
        # output can only have come from the signed payload.
        self.assertEqual(data["parameters"]["ema_half_life_days"], 45.0)
        self.assertEqual(len(data["recommended_claim_order"]), 2)
        # The fake immunity dict is gone from the consequence verb's output.
        self.assertNotIn("constitutional_immunity", data)
        self.assertNotIn('"status": "PASS"', r.stdout)

    def test_half_life_flag_refused_even_when_activated(self):
        self.enroll()
        path = self.write_constitutional(activation="on", half_life=45.0)
        sign(path, self.operator_key)
        # Refused even when the flag AGREES with the file: the rule is
        # positional (constitutional params come from the file), not
        # value-dependent, so there is no knob to probe.
        r = self.dispatch("--half-life-days", "45.0")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("CONSTITUTIONAL parameter", r.stderr)
        r2 = self.dispatch("--half-life-days", "1.0")
        self.assertEqual(r2.returncode, 1, r2.stdout)

    def test_signed_weights_reach_the_score(self):
        """Two dispatches, identical stores, two signed weight sets: a record
        authored by worker-a moves worker-a's score only under the second
        file. The parameter provably flows from the signature to the figure."""
        self.enroll()
        rec = {"id": "PR-900", "status": "active", "published_by": "worker-a",
               "published_at": "2026-08-20T00:00:00Z", "tier": 2,
               "subject": "fixture", "ratio": "fixture"}
        (self.root / "precedents" / "PR-900.json").write_text(
            json.dumps(rec), encoding="utf-8")

        path = self.write_constitutional(
            activation="on", half_life=45.0,
            weights={"rule_authorship": 1.0, "citations_received": 1.0,
                     "consolidations": 2.0, "overrulings_sustained": 1.5,
                     "verdicts_upheld": 1.0})
        sign(path, self.operator_key)
        r1 = self.dispatch("--now", "2026-08-20T00:00:00Z")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        score1 = json.loads(r1.stdout)["candidates"][0]["total_score"]

        path = self.write_constitutional(
            activation="on", half_life=45.0,
            weights={"rule_authorship": 3.0, "citations_received": 1.0,
                     "consolidations": 2.0, "overrulings_sustained": 1.5,
                     "verdicts_upheld": 1.0})
        sign(path, self.operator_key)
        r2 = self.dispatch("--now", "2026-08-20T00:00:00Z")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        score2 = json.loads(r2.stdout)["candidates"][0]["total_score"]

        self.assertEqual(json.loads(r1.stdout)["candidates"][0]["identity"], "worker-a")
        self.assertAlmostEqual(score2, score1 * 3.0, places=3)


class VerificationIsBoundToTheBytesNotTheFile(GateFixture):
    """T-420 round 2, the TOCTOU escape. The prior code read the constitutional
    file twice -- once for the payload, once inside signature verification --
    with check_anchor's subprocess in the window, so a same-OS-user process
    (D-17) could swap the bytes between the reads and make a forged activated
    payload verify against the genuine signed bytes. The fix reads once and
    threads the bytes through; these tests pin that verification is bound to
    the argument bytes, and that the payload is read exactly once."""

    def test_verify_uses_argument_bytes_even_if_the_file_is_swapped(self):
        self.enroll()
        path = self.write_constitutional(activation="on", half_life=45.0)
        sig = sign(path, self.operator_key)
        genuine = path.read_bytes()
        # Swap the file to garbage. Verifying the GENUINE bytes still succeeds,
        # because verification never re-reads the file.
        path.write_bytes(b"{}not-the-signed-bytes")
        fp = rep._verify_constitutional_signature(self.root, genuine, sig)
        self.assertTrue(fp)
        # Restore the genuine file. Verifying TAMPERED bytes still FAILS,
        # because verification is bound to the bytes passed in, not the file.
        path.write_bytes(genuine)
        with self.assertRaises(w.TrustError):
            rep._verify_constitutional_signature(self.root, genuine + b" ", sig)

    def test_constitutional_status_reads_the_payload_exactly_once(self):
        tree = ast.parse(REPUTATION_PY.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_constitutional_status")
        reads = [c for c in ast.walk(fn)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                 and c.func.attr in ("read_bytes", "read_text")]
        opens = [c for c in ast.walk(fn)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                 and c.func.id == "open"]
        self.assertEqual(len(reads), 1,
                         "the constitutional payload must be read exactly once (TOCTOU)")
        self.assertEqual(opens, [], "no second read of the payload via open()")

    def test_swap_after_verify_cannot_return_a_forged_payload(self):
        """End to end: a VERIFIED, activated file, then the on-disk bytes are
        swapped to an activated forgery with no valid signature. Because status
        is derived from the single read, the module cannot return the forgery
        as verified -- it either reports the genuine payload or fails."""
        self.enroll()
        path = self.write_constitutional(activation="off", half_life=45.0)
        sign(path, self.operator_key)
        # Forge an activated payload with the SAME namespace but no re-sign.
        forged = json.dumps({"schema_version": 1, "namespace": rep.CONSTITUTIONAL_NAMESPACE,
                             "activation": "on", "ema_half_life_days": 9999.0,
                             "weights": {"rule_authorship": 500.0}}).encode("utf-8")
        path.write_bytes(forged)
        payload, st = rep._phase_b_activation(self.root)
        # The forged bytes do not carry a valid signature, so activation refuses.
        self.assertIsNone(payload)
        self.assertEqual(st["state"], "BAD_SIGNATURE")


class ConsolidationsDecayLikeEveryOtherComponent(GateFixture):
    """T-420 round 2, the decay-evasion escape. decayed_f3 (consolidations) was
    the raw count times a weight, with no EMA decay -- a permanent, non-decaying
    floor that let a dormant identity outrank active ones forever. Now it decays
    by the consolidated record's own timestamp, like f1/f2/f4/f5."""

    def _seed_consolidation(self, author, when):
        recs = {"PR-900": {"id": "PR-900", "status": "active", "published_by": author,
                          "published_at": when, "tier": 2, "subject": "s", "ratio": "r"}}
        for i, follower in enumerate(("follower-1", "follower-2", "follower-3")):
            pid = "PR-90%d" % (i + 1)
            recs[pid] = {"id": pid, "status": "active", "published_by": follower,
                        "published_at": when, "tier": 2, "subject": "s", "ratio": "r",
                        "relations": [{"target": "PR-900", "type": "follows",
                                       "below_target_tier": False}]}
        for pid, r in recs.items():
            (self.root / "precedents" / (pid + ".json")).write_text(
                json.dumps(r), encoding="utf-8")

    def test_a_years_old_consolidation_does_not_hold_a_permanent_floor(self):
        self._seed_consolidation("worker-a", "2020-01-01T00:00:00Z")
        precedents = rep.load_precedents(self.root)
        bb = rep.load_blackboard_tasks(self.root)
        reopened = rep.load_reopened_tasks(self.root)
        # Sanity: the record really is consolidated (3 qualifying applications).
        f3 = rep.figure_consolidations_achieved("worker-a", precedents)
        self.assertEqual(f3["value"], 1)

        fresh = rep._compute_phase_b_figures(
            "worker-a", self.root, precedents, bb, reopened, half_life_days=30.0,
            now_dt=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc))
        later = rep._compute_phase_b_figures(
            "worker-a", self.root, precedents, bb, reopened, half_life_days=30.0,
            now_dt=dt.datetime(2020, 9, 1, tzinfo=dt.timezone.utc))  # ~8 half-lives
        c_fresh = fresh["decayed_components"]["consolidations"]
        c_later = later["decayed_components"]["consolidations"]
        self.assertGreater(c_fresh, 0.0)
        self.assertLess(c_later, 0.05 * c_fresh,
                        "consolidations must decay, not sit as a permanent floor")


class RankStaysAConsequenceFreeReport(GateFixture):

    def test_rank_runs_without_any_constitutional_file(self):
        r = run_cli("rank", "--root", str(self.root), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("reporting only", data["consequence"])
        self.assertFalse(data["parameters_ratified"])
        self.assertEqual(data["constitutional_file_state"], "NOT_PRESENT")

    def test_rank_labels_trial_parameters_not_ratified(self):
        self.enroll()
        path = self.write_constitutional(activation="off", half_life=45.0)
        sign(path, self.operator_key)
        r = run_cli("rank", "--root", str(self.root), "--half-life-days", "7", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertFalse(data["parameters_ratified"])
        self.assertEqual(data["constitutional_file_state"], "VERIFIED")

    def test_rank_labels_matching_parameters_ratified_even_when_activation_off(self):
        """Ratification of parameters and activation of consequences are
        separate operator acts; rank reports the first without the second."""
        self.enroll()
        path = self.write_constitutional(activation="off", half_life=45.0)
        sign(path, self.operator_key)
        r = run_cli("rank", "--root", str(self.root), "--half-life-days", "45", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertTrue(data["parameters_ratified"])


class AuditImmunityEmitsFiguresNotVerdicts(GateFixture):

    def test_no_verdict_and_the_hardcoded_pass_dict_is_gone(self):
        self.enroll()
        r = run_cli("audit-immunity", "--root", str(self.root), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIsNone(data["verdict"])
        self.assertNotIn("status", data)
        self.assertNotIn("constitutional_invariants", data)
        self.assertEqual(
            data["mechanically_checked"]["constitutional_file_state"], "NOT_PRESENT")
        for key in ("verification_burdens_uniform", "quorum_floors_unmodulated",
                    "no_stored_balances", "D-17_shared_os_user"):
            self.assertIn(key, data["not_mechanically_evaluable"])

    def test_text_mode_never_prints_an_overall_pass(self):
        self.enroll()
        r = run_cli("audit-immunity", "--root", str(self.root))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("OVERALL STATUS", r.stdout)
        self.assertNotIn("PASS", r.stdout)
        self.assertIn("NO VERDICT", r.stdout)
        self.assertIn("NOT MECHANICALLY EVALUABLE", r.stdout)

    def test_reports_the_verified_state_when_it_holds(self):
        self.enroll()
        path = self.write_constitutional(activation="on", half_life=45.0)
        sign(path, self.operator_key)
        r = run_cli("audit-immunity", "--root", str(self.root), "--json")
        data = json.loads(r.stdout)
        checked = data["mechanically_checked"]
        self.assertEqual(checked["constitutional_file_state"], "VERIFIED")
        self.assertEqual(checked["activation"], "on")
        self.assertEqual(checked["signed_parameters"]["ema_half_life_days"], 45.0)
        self.assertIsNone(data["verdict"])


class LiveRootSmoke(unittest.TestCase):
    """Against the LIVE .harness/: state-agnostic on purpose, so these stay
    green before AND after the operator signs a real constitutional file."""

    def test_rank_reports_and_says_no_consequence(self):
        r = run_cli("rank", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["authority"], "PR-061 (RAT-01) / PR-060")
        self.assertIn("self-asserted", data["caveat"])  # T-421: Phase B carries the caveat too
        self.assertIn("reporting only", data["consequence"])
        scores = [item["total_score"] for item in data["rankings"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_dispatch_is_gated_or_authorized_never_silently_open(self):
        r = run_cli("dispatch", "--candidates", "worker-a,worker-b", "--json")
        if r.returncode == 0:
            data = json.loads(r.stdout)
            self.assertEqual(data["constitutional_file"]["state"], "VERIFIED")
            self.assertEqual(data["parameters"]["source"], "signed constitutional file")
        else:
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("consequence verb", r.stderr)


class NoCodePathCanMintTheConstitutionalFile(unittest.TestCase):
    """warrant.py's discipline, applied here: a test asserts the module is
    UNABLE to do the forbidden thing, not merely that it currently doesn't."""

    WRITE_ATTRS = {"write_text", "write_bytes", "unlink", "mkdir", "rmdir",
                   "replace", "rename", "touch", "symlink_to", "chmod",
                   "atomic_write_json", "append_jsonl", "log_event", "guarded",
                   "remove", "removedirs", "rmtree", "copyfile", "copy",
                   "makedirs"}

    def _parsed(self):
        return ast.parse(REPUTATION_PY.read_text(encoding="utf-8"))

    def _calls_with_enclosing_function(self, tree):
        found = []
        def walk(node, fn):
            for child in ast.iter_child_nodes(node):
                child_fn = fn
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    child_fn = child.name
                if isinstance(child, ast.Call):
                    name = None
                    if isinstance(child.func, ast.Attribute):
                        name = child.func.attr
                    elif isinstance(child.func, ast.Name):
                        name = child.func.id
                    found.append((child_fn, name, child))
                walk(child, child_fn)
        walk(tree, "<module>")
        return found

    def test_exhaustive_map_of_write_capable_calls(self):
        """The full map of write-capable call sites in reputation.py is ONE
        entry: the allowed_signers rebuild inside _verify_constitutional_
        signature, whose target lives in a system temp dir (asserted below),
        never in the repository. An allow-set would rot; the exhaustive map
        breaks loudly the moment anyone adds a second write."""
        tree = self._parsed()
        writers = []
        for fn, name, call in self._calls_with_enclosing_function(tree):
            if name in self.WRITE_ATTRS:
                writers.append((fn, name))
            if name == "open":
                for arg in list(call.args)[1:] + [kw.value for kw in call.keywords]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                            and any(m in arg.value for m in "wax+"):
                        writers.append((fn, "open:" + arg.value))
        self.assertEqual(writers,
                         [("_verify_constitutional_signature", "write_text")])

    def test_the_one_write_targets_a_system_temp_dir(self):
        tree = self._parsed()
        temp_calls = [
            (fn, name) for fn, name, _ in self._calls_with_enclosing_function(tree)
            if name == "TemporaryDirectory"]
        self.assertEqual(temp_calls,
                         [("_verify_constitutional_signature", "TemporaryDirectory")])

    def test_no_code_path_can_sign(self):
        """Every `ssh-keygen -Y <mode>` literal in the module is verify."""
        tree = self._parsed()
        y_modes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.List, ast.Tuple)):
                elts = [e.value for e in node.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                for i, val in enumerate(elts):
                    if val == "-Y" and i + 1 < len(elts):
                        y_modes.append(elts[i + 1])
        self.assertEqual(y_modes, ["verify"])

    def test_the_warrant_namespace_is_never_borrowed(self):
        self.assertNotEqual(rep.CONSTITUTIONAL_NAMESPACE, w.NAMESPACE)
        self.assertEqual(rep.CONSTITUTIONAL_NAMESPACE, "harness-constitutional")
        tree = self._parsed()
        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and n.value == "harness-warrant"]
        self.assertEqual(literals, [])


class ZeroWritesAcrossPhaseB(GateFixture):
    """AD2-54 extended to the Phase B verbs: snapshot-hash the fixture root,
    run every verb on every output path -- INCLUDING the activated
    consequence verb -- and require byte-identical stores after."""

    def _snapshot(self):
        return {
            str(p.relative_to(self.root)): sha256_of(p)
            for p in sorted(self.root.rglob("*")) if p.is_file()
        }

    def test_every_phase_b_verb_writes_nothing(self):
        self.enroll()
        path = self.write_constitutional(activation="on", half_life=45.0)
        sign(path, self.operator_key)
        before = self._snapshot()
        invocations = [
            ["rank", "--root", str(self.root)],
            ["rank", "--root", str(self.root), "--json"],
            ["rank", "--root", str(self.root), "--half-life-days", "7"],
            ["dispatch", "--root", str(self.root), "--candidates", "a,b"],
            ["dispatch", "--root", str(self.root), "--candidates", "a,b", "--json"],
            ["dispatch", "--root", str(self.root), "--candidates", "a,b",
             "--half-life-days", "45.0"],
            ["audit-immunity", "--root", str(self.root)],
            ["audit-immunity", "--root", str(self.root), "--json"],
        ]
        for args in invocations:
            result = run_cli(*args)
            self.assertIn(result.returncode, (0, 1, 4),
                          "{} -> {}".format(args, result.returncode))
        self.assertEqual(before, self._snapshot())


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
