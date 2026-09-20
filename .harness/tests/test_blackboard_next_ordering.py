"""test_blackboard_next_ordering.py -- T-422: pins cmd_next/cmd_claim/cmd_status's
CURRENT contract, then exercises the Phase B claim-order CONSUMER SEAM added by
this task (`blackboard.live_candidates` / `blackboard.phase_b_claim_order` /
`blackboard.phase_b_advisory_line`) with NO consequence attached.

Cites PR-061 (RAT-01, the ruling that authorizes `reputation.py dispatch` at
all) and PR-060 clause 6 (constitutional vs. operational parameter split).
Docket C-002 / T-424 decides whether/how any consequence ever attaches to
this advisory; T-426 is the wiring task if accepted. This suite only proves
the READ side is correct and safe: the existing sort/candidate-selection
output is byte-for-byte unchanged, the advisory line never crashes the
dispatcher, and it never writes anything.

Two fixture bases:
  * `PinnedContractFixture` -- no keys, no gate; a scratch blackboard.json
    only. Pins today's priority/id ordering, the missing-priority default,
    the review->verifier routing, the engine 'any' pass-through, claim
    first-come-first-served, and zero writes from `next`/`status`.
  * `PhaseBAdvisoryFixture` -- copies `GateFixture` from
    test_reputation_phase_b.py (real ed25519 keypair standing in for the
    operator's off-machine key, a real enrolled trust anchor, a real signed
    constitutional file) and additionally redirects every hc.* binding
    blackboard.py's commands actually touch: hc.HARNESS alone is NOT enough
    -- BLACKBOARD/STATE/TASKS/EVENTS/GUARD are all bound at import time in
    harness_common.py's own module namespace, and reassigning HARNESS after
    import does not retarget them.

Requires ssh-keygen (already a hard dependency of test_reputation_phase_b.py
and warrant.py's own suite).
"""
import argparse
import contextlib
import datetime as dt
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
TESTS_DIR = ROOT / ".harness" / "tests"
REPUTATION_PY = BIN_DIR / "reputation.py"

sys.path.insert(0, str(BIN_DIR))
sys.path.insert(0, str(TESTS_DIR))

import harness_common as hc  # noqa: E402
import blackboard as bbmod  # noqa: E402
import reputation as rep  # noqa: E402
import warrant as w  # noqa: E402
import test_reputation_phase_b as trpb  # noqa: E402 -- GateFixture, keygen, sign


# --------------------------------------------------------------------------
# shared task-dict builder
# --------------------------------------------------------------------------

def task(status="open", role="worker", engine="any", priority=None, claimed_by=None,
         claim_expires_at=None, depends_on=None, created_by="creator", title="a task"):
    d = {
        "status": status, "role": role, "engine": engine, "title": title,
        "depends_on": depends_on or [], "created_by": created_by,
    }
    if priority is not None:
        d["priority"] = priority
    if claimed_by is not None:
        d["claimed_by"] = claimed_by
    if claim_expires_at is not None:
        d["claim_expires_at"] = claim_expires_at
    return d


def empty_bb():
    return {"generation": 1, "updated_at": "x", "updated_by": "x", "tasks": {}}


# --------------------------------------------------------------------------
# Fixture 1: pinned contract, no gate involved at all
# --------------------------------------------------------------------------

class PinnedContractFixture(unittest.TestCase):
    """Redirects the SAME six hc.* bindings the gate fixture below does, but
    never touches keys/trust/constitutional -- the Phase B gate stays CLOSED
    (no constitutional file exists), which is exactly today's default state
    for every consumer that hasn't enrolled a trust anchor."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.harness = pathlib.Path(self._tmp.name) / "harness"
        (self.harness / "tasks").mkdir(parents=True)
        (self.harness / "logs").mkdir()

        self._orig = {name: getattr(hc, name) for name in
                       ("HARNESS", "BLACKBOARD", "STATE", "TASKS", "EVENTS", "GUARD")}
        hc.HARNESS = self.harness
        hc.BLACKBOARD = self.harness / "blackboard.json"
        hc.STATE = self.harness / "state.json"
        hc.TASKS = self.harness / "tasks"
        hc.EVENTS = self.harness / "logs" / "events.jsonl"
        hc.GUARD = self.harness / "locks" / ".guard"
        self.addCleanup(self._restore)

        hc.atomic_write_json(hc.BLACKBOARD, empty_bb())

    def _restore(self):
        for name, value in self._orig.items():
            setattr(hc, name, value)

    def set_tasks(self, tasks):
        bb = hc.read_json(hc.BLACKBOARD)
        bb["tasks"] = tasks
        hc.atomic_write_json(hc.BLACKBOARD, bb)

    def run_next(self, agent="tester", role=None, engine=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bbmod.cmd_next(argparse.Namespace(agent=agent, role=role, engine=engine))
        return code, buf.getvalue()

    def run_status(self, agent="tester"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bbmod.cmd_status(argparse.Namespace(agent=agent))
        return code, buf.getvalue()

    def run_claim(self, task_id, agent):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bbmod.cmd_claim(argparse.Namespace(task_id=task_id, agent=agent, lease=None))
        return code, buf.getvalue()


class PriorityAndIdOrdering(PinnedContractFixture):

    def test_lower_priority_number_wins_regardless_of_id(self):
        # T-9 (priority 1) must beat T-1 (priority 3): id ordering alone
        # would pick the wrong one if priority weren't the primary key.
        self.set_tasks({
            "T-9": task(priority=1, title="urgent"),
            "T-1": task(priority=3, title="not urgent"),
        })
        _, out = self.run_next()
        self.assertIn("next: T-9 ", out)

    def test_id_breaks_priority_ties(self):
        self.set_tasks({
            "T-9": task(priority=2, title="second alphabetically-late"),
            "T-1": task(priority=2, title="first"),
        })
        _, out = self.run_next()
        self.assertIn("next: T-1 ", out)

    def test_missing_priority_defaults_to_five_and_ties_with_explicit_five(self):
        # T-1 carries an explicit priority=5; T-2 carries NO priority key at
        # all. If missing-priority didn't default to 5 they wouldn't tie, and
        # id-ascending wouldn't decide between them.
        self.set_tasks({
            "T-1": task(priority=5, title="explicit five"),
            "T-2": task(title="no priority key at all"),
        })
        self.assertNotIn("priority", self.harness_task("T-2"))
        _, out = self.run_next()
        self.assertIn("next: T-1 ", out)
        self.assertIn("priority 5", out)

    def harness_task(self, task_id):
        return hc.read_json(hc.BLACKBOARD)["tasks"][task_id]


class ReviewRoutesToVerifierOnly(PinnedContractFixture):

    def test_review_task_excluded_when_role_filter_is_worker(self):
        self.set_tasks({"T-5": task(status="review", role="worker", title="up for review")})
        code, out = self.run_next(role="worker")
        self.assertEqual(code, 1)
        self.assertIn("no claimable task", out)

    def test_review_task_included_when_role_filter_is_verifier(self):
        self.set_tasks({"T-5": task(status="review", role="worker", title="up for review")})
        code, out = self.run_next(role="verifier")
        self.assertEqual(code, 0)
        self.assertIn("next: T-5 ", out)

    def test_review_task_included_when_no_role_filter_given(self):
        self.set_tasks({"T-5": task(status="review", role="worker", title="up for review")})
        code, out = self.run_next(role=None)
        self.assertEqual(code, 0)
        self.assertIn("next: T-5 ", out)


class EngineAnyPassesThrough(PinnedContractFixture):

    def test_task_engine_any_passes_a_specific_engine_filter(self):
        self.set_tasks({"T-1": task(engine="any", priority=1)})
        code, out = self.run_next(engine="claude")
        self.assertEqual(code, 0)
        self.assertIn("next: T-1 ", out)

    def test_task_engine_mismatch_is_excluded(self):
        self.set_tasks({"T-1": task(engine="gemini", priority=1)})
        code, out = self.run_next(engine="claude")
        self.assertEqual(code, 1)
        self.assertIn("no claimable task", out)


class ClaimIsFirstCome(PinnedContractFixture):

    def test_second_claimant_is_refused(self):
        self.set_tasks({"T-1": task(status="open", priority=1)})
        code, out = self.run_claim("T-1", "agent-a")
        self.assertEqual(code, 0)
        self.assertIn("claimed T-1 for agent-a", out)
        with self.assertRaises(SystemExit) as ctx:
            self.run_claim("T-1", "agent-b")
        self.assertIn("not claimable", str(ctx.exception))
        self.assertIn("agent-a", str(ctx.exception))


class ZeroWriteAssertionForNextAndStatus(PinnedContractFixture):
    """AD2-54's discipline, extended to blackboard.py's own read paths (T-422
    item 1): neither `next` nor `status` may write blackboard.json when no
    lease has actually expired -- the Phase B advisory line this task adds
    is read-only end to end."""

    def _snapshot(self):
        return hc.BLACKBOARD.read_bytes() if hc.BLACKBOARD.exists() else None

    def test_next_writes_nothing(self):
        self.set_tasks({"T-1": task(priority=1)})
        before = self._snapshot()
        self.run_next()
        self.assertEqual(before, self._snapshot())

    def test_status_writes_nothing(self):
        self.set_tasks({"T-1": task(priority=1), "T-2": task(status="review")})
        before = self._snapshot()
        self.run_status()
        self.assertEqual(before, self._snapshot())

    def test_next_with_no_claimable_task_writes_nothing(self):
        self.set_tasks({"T-1": task(status="open", role="worker",
                                    depends_on=["T-missing"])})
        before = self._snapshot()
        code, out = self.run_next()
        self.assertEqual(code, 1)
        self.assertEqual(before, self._snapshot())


# --------------------------------------------------------------------------
# live_candidates: unit-tested directly against raw bb dicts (T-422 item 3)
# --------------------------------------------------------------------------

class LiveCandidatesDefinition(unittest.TestCase):
    """'Live candidates' (T-422's documented definition): identities holding
    an UNEXPIRED claim in blackboard.json (status claimed/in_progress, and
    claim_expires_at either unset or still in the future) PLUS the
    requesting --agent, deduplicated."""

    def test_includes_claimed_and_in_progress_holders_plus_agent(self):
        future = hc.iso_in(3600)
        bb = {"tasks": {
            "T-1": task(status="claimed", claimed_by="worker-a", claim_expires_at=future),
            "T-2": task(status="in_progress", claimed_by="worker-b", claim_expires_at=future),
        }}
        self.assertEqual(bbmod.live_candidates(bb, "worker-c"),
                         ["worker-a", "worker-b", "worker-c"])

    def test_excludes_open_and_review_tasks(self):
        bb = {"tasks": {
            "T-1": task(status="open", claimed_by=None),
            "T-2": task(status="review", claimed_by="worker-x"),
        }}
        self.assertEqual(bbmod.live_candidates(bb, "worker-c"), ["worker-c"])

    def test_excludes_expired_claims(self):
        past = hc.iso_in(-3600)
        bb = {"tasks": {"T-1": task(status="claimed", claimed_by="worker-a",
                                    claim_expires_at=past)}}
        self.assertEqual(bbmod.live_candidates(bb, "worker-c"), ["worker-c"])

    def test_unset_expiry_counts_as_unexpired(self):
        bb = {"tasks": {"T-1": task(status="claimed", claimed_by="worker-a")}}
        self.assertEqual(bbmod.live_candidates(bb, "worker-c"), ["worker-a", "worker-c"])

    def test_dedups_the_requesting_agent_against_a_holder(self):
        future = hc.iso_in(3600)
        bb = {"tasks": {"T-1": task(status="claimed", claimed_by="worker-a",
                                    claim_expires_at=future)}}
        self.assertEqual(bbmod.live_candidates(bb, "worker-a"), ["worker-a"])

    def test_no_live_claims_and_no_agent_is_empty(self):
        bb = {"tasks": {}}
        self.assertEqual(bbmod.live_candidates(bb, None), [])


# --------------------------------------------------------------------------
# phase_b_claim_order: seam contract -- never raises, never leaks
# --half-life-days, never imports reputation.py in-process
# --------------------------------------------------------------------------

class SeamContract(unittest.TestCase):

    def test_reputation_py_path_is_fixed_by_this_files_own_location(self):
        # Never derived from hc.HARNESS -- that is the DATA root (redirected
        # by every fixture above); the SCRIPT lives next to blackboard.py.
        self.assertEqual(bbmod._REPUTATION_PY, BIN_DIR / "reputation.py")
        self.assertTrue(bbmod._REPUTATION_PY.is_file())

    def test_blackboard_py_never_imports_reputation_in_process(self):
        src = (BIN_DIR / "blackboard.py").read_text(encoding="utf-8")
        self.assertNotIn("import reputation", src)
        self.assertNotIn("from reputation", src)

    def test_never_passes_half_life_days(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            out = json.dumps({"recommended_claim_order": ["a", "b"]})
            return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

        with mock.patch.object(bbmod.subprocess, "run", side_effect=fake_run):
            order, reason = bbmod.phase_b_claim_order(["a", "b"])
        self.assertEqual(order, ["a", "b"])
        self.assertNotIn("--half-life-days", captured["argv"])
        self.assertIn("--json", captured["argv"])
        self.assertIn("dispatch", captured["argv"])
        self.assertIn("--candidates", captured["argv"])
        self.assertEqual(captured["argv"][0], sys.executable)

    def test_no_candidates_short_circuits_without_a_subprocess_call(self):
        with mock.patch.object(bbmod.subprocess, "run") as m:
            order, reason = bbmod.phase_b_claim_order([])
        m.assert_not_called()
        self.assertIsNone(order)
        self.assertEqual(reason, "no live candidates")

    def test_never_raises_when_subprocess_run_itself_raises(self):
        with mock.patch.object(bbmod.subprocess, "run",
                               side_effect=OSError("reputation.py vanished")):
            order, reason = bbmod.phase_b_claim_order(["a"])
        self.assertIsNone(order)
        self.assertIn("reputation.py dispatch could not run", reason)

    def test_never_raises_on_malformed_json_stdout(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="{not json", stderr="")

        with mock.patch.object(bbmod.subprocess, "run", side_effect=fake_run):
            order, reason = bbmod.phase_b_claim_order(["a"])
        self.assertIsNone(order)
        self.assertIn("could not be parsed", reason)

    def test_never_raises_on_empty_stdout_at_exit_zero(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        with mock.patch.object(bbmod.subprocess, "run", side_effect=fake_run):
            order, reason = bbmod.phase_b_claim_order(["a"])
        self.assertIsNone(order)
        self.assertIn("no stdout", reason)

    def test_reason_extracted_from_stderr_line_two(self):
        stderr = ("refused: dispatch is a consequence verb (PR-061) and no verified, "
                   "activated constitutional file authorizes it\n"
                   "  constitutional file: NOT_PRESENT -- no constitutional file at /x\n"
                   "  activation is the operator's act alone: ...\n")
        reason = bbmod._phase_b_reason_from_stderr(stderr, 1)
        self.assertEqual(reason, "NOT_PRESENT -- no constitutional file at /x")

    def test_reason_falls_back_to_exit_code_when_no_second_line(self):
        reason = bbmod._phase_b_reason_from_stderr("REGISTRY INTEGRITY ERROR: bad\n", 4)
        self.assertEqual(reason, "dispatch exited 4")

    def test_advisory_line_shape_when_order_present(self):
        with mock.patch.object(bbmod, "phase_b_claim_order",
                               return_value=(["a", "b"], "VERIFIED, activation on")):
            line = bbmod.phase_b_advisory_line({"tasks": {}}, "agent-x")
        self.assertEqual(line, "phase-b claim order: a, b (VERIFIED, activation on)")

    def test_advisory_line_shape_when_order_absent(self):
        with mock.patch.object(bbmod, "phase_b_claim_order",
                               return_value=(None, "NOT_PRESENT -- no constitutional file")):
            line = bbmod.phase_b_advisory_line({"tasks": {}}, "agent-x")
        self.assertEqual(line, "phase-b claim order not applied: NOT_PRESENT -- no constitutional file")


# --------------------------------------------------------------------------
# Fixture 2: the real gate, copied from test_reputation_phase_b.GateFixture
# --------------------------------------------------------------------------

class PhaseBAdvisoryFixture(unittest.TestCase):
    """A scratch harness root with a REAL enrolled trust anchor (an ed25519
    keypair standing in for the operator's off-machine key), laid out
    exactly like `hc.HARNESS` itself (precedents/, tasks/, blackboard.json,
    logs/events.jsonl, plus constitutional/ and trust/ as siblings) so the
    SAME root value blackboard.py passes as `--root` to `reputation.py
    dispatch` is valid for both. Redirects every hc.* binding blackboard.py's
    commands touch, not just hc.HARNESS."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.harness = self.base / "harness"
        (self.harness / "precedents").mkdir(parents=True)
        (self.harness / "tasks").mkdir()
        (self.harness / "logs").mkdir()
        self.keys = self.base / "keys"
        self.keys.mkdir()
        self.operator_key = self.keys / "operator"
        self.operator_pub = trpb.keygen(self.operator_key, "operator@offmachine")

        self._orig = {name: getattr(hc, name) for name in
                       ("HARNESS", "BLACKBOARD", "STATE", "TASKS", "EVENTS", "GUARD")}
        hc.HARNESS = self.harness
        hc.BLACKBOARD = self.harness / "blackboard.json"
        hc.STATE = self.harness / "state.json"
        hc.TASKS = self.harness / "tasks"
        hc.EVENTS = self.harness / "logs" / "events.jsonl"
        hc.GUARD = self.harness / "locks" / ".guard"
        self.addCleanup(self._restore)

        hc.atomic_write_json(hc.BLACKBOARD, empty_bb())
        # `guarded()` always creates/opens this flock file as a side effect of
        # ANY blackboard.py command (pre-existing behaviour, unrelated to
        # T-422) -- pre-touch it so the zero-write snapshot below starts from
        # the same steady state `dispatch`'s own ZeroWritesAcrossPhaseB does.
        hc.GUARD.parent.mkdir(parents=True, exist_ok=True)
        hc.GUARD.touch()

    def _restore(self):
        for name, value in self._orig.items():
            setattr(hc, name, value)

    def enroll(self):
        td = self.harness / "trust"
        td.mkdir(exist_ok=True)
        pub_line = self.operator_pub.read_text(encoding="utf-8").strip()
        (td / "root.pub").write_text(pub_line + "\n", encoding="utf-8")
        (td / "root.fingerprint").write_text(
            w.key_fingerprint(self.operator_pub) + "\n", encoding="utf-8")

    def write_constitutional(self, activation="on", half_life=45.0, weights=None,
                             namespace=rep.CONSTITUTIONAL_NAMESPACE):
        cdir = self.harness / "constitutional"
        cdir.mkdir(exist_ok=True)
        path = cdir / "reputation.json"
        payload = {
            "schema_version": 1, "namespace": namespace,
            "subject": "reputation-phase-b", "authority": "PR-061 (RAT-01) / PR-060",
            "activation": activation, "ema_half_life_days": half_life,
            "weights": weights or {"rule_authorship": 1.0, "citations_received": 1.0,
                                   "consolidations": 2.0, "overrulings_sustained": 1.5,
                                   "verdicts_upheld": 1.0},
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def set_tasks(self, tasks):
        bb = hc.read_json(hc.BLACKBOARD)
        bb["tasks"] = tasks
        hc.atomic_write_json(hc.BLACKBOARD, bb)

    def run_next(self, agent="tester", role=None, engine=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bbmod.cmd_next(argparse.Namespace(agent=agent, role=role, engine=engine))
        return code, buf.getvalue()

    def run_status(self, agent="tester"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bbmod.cmd_status(argparse.Namespace(agent=agent))
        return code, buf.getvalue()

    def dispatch_directly(self, candidates):
        """Independent cross-check: calls the real `dispatch --json` CLI the
        same way blackboard.py's seam does, so a test can assert the
        advisory equals dispatch's OWN answer rather than re-deriving it."""
        proc = subprocess.run(
            [sys.executable, str(REPUTATION_PY), "dispatch", "--json",
             "--root", str(self.harness), "--candidates", ",".join(candidates)],
            capture_output=True, text=True)
        return proc


class GateClosedAdvisory(PhaseBAdvisoryFixture):
    """No constitutional file at all -- the everyday state for any root that
    has never enrolled a trust anchor. dispatch's own state token is
    NOT_PRESENT (checked before enrollment is even considered)."""

    def test_same_task_selection_plus_reason_with_state_token(self):
        self.set_tasks({"T-1": task(priority=1, title="only task")})
        code, out = self.run_next(agent="tester")
        self.assertEqual(code, 0)
        self.assertIn("next: T-1 ", out)
        self.assertIn("claim it: python3 .harness/bin/blackboard.py claim T-1 --agent tester", out)
        self.assertIn("phase-b claim order not applied:", out)
        self.assertIn("NOT_PRESENT", out)

    def test_status_also_prints_the_same_reason(self):
        self.set_tasks({"T-1": task(priority=1)})
        code, out = self.run_status(agent="tester")
        self.assertEqual(code, 0)
        self.assertIn("phase-b claim order not applied:", out)
        self.assertIn("NOT_PRESENT", out)


class GateOpenAdvisory(PhaseBAdvisoryFixture):

    def test_advisory_order_equals_dispatch_json_for_the_same_candidates(self):
        self.enroll()
        path = self.write_constitutional(activation="on", half_life=45.0)
        trpb.sign(path, self.operator_key)
        future = hc.iso_in(3600)
        self.set_tasks({
            "T-1": task(status="claimed", claimed_by="worker-x", claim_expires_at=future,
                       priority=1, title="held"),
        })
        candidates = bbmod.live_candidates(hc.read_json(hc.BLACKBOARD), "worker-y")
        self.assertEqual(candidates, ["worker-x", "worker-y"])
        expected = self.dispatch_directly(candidates)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        expected_order = json.loads(expected.stdout)["recommended_claim_order"]

        code, out = self.run_status(agent="worker-y")
        self.assertEqual(code, 0)
        self.assertIn(
            "phase-b claim order: {} (VERIFIED, activation on)".format(", ".join(expected_order)),
            out)

    def test_existing_next_selection_is_unchanged_by_an_open_gate(self):
        self.enroll()
        path = self.write_constitutional(activation="on")
        trpb.sign(path, self.operator_key)
        self.set_tasks({
            "T-9": task(priority=1, title="urgent"),
            "T-1": task(priority=3, title="not urgent"),
        })
        code, out = self.run_next(agent="worker-y")
        self.assertEqual(code, 0)
        self.assertIn("next: T-9 ", out)
        self.assertIn("phase-b claim order:", out)
        self.assertIn("VERIFIED, activation on", out)


class TiesAndUnknownIdentities(PhaseBAdvisoryFixture):
    """Documented behaviour (T-422 item 5): unknown identities (no precedent
    or task history at all) score 0 in every figure; `dispatch`'s own
    tie-break is (-score, identity) -- alphabetical among ties.
    blackboard.py implements NO tie-break of its own -- it prints
    `recommended_claim_order` verbatim."""

    def test_two_unknown_identities_tie_and_break_alphabetically(self):
        self.enroll()
        path = self.write_constitutional(activation="on")
        trpb.sign(path, self.operator_key)
        future = hc.iso_in(3600)
        self.set_tasks({
            "T-1": task(status="claimed", claimed_by="zzz-unknown", claim_expires_at=future),
        })
        code, out = self.run_status(agent="aaa-unknown")
        self.assertEqual(code, 0)
        self.assertIn("phase-b claim order: aaa-unknown, zzz-unknown (VERIFIED, activation on)", out)


class DispatchNonZeroExitsNeverCrashBlackboard(PhaseBAdvisoryFixture):
    """T-422 item 5: dispatch exit 4 (corrupt precedent) and exit 1 (gate
    closed) both fold into a printed reason -- never a crash, and never a
    change to today's task selection."""

    def test_exit_1_gate_closed_no_crash_todays_order_reason_printed(self):
        self.set_tasks({"T-1": task(priority=1, title="only task")})
        code, out = self.run_next(agent="tester")
        self.assertEqual(code, 0)
        self.assertIn("next: T-1 ", out)
        self.assertIn("phase-b claim order not applied:", out)

    def test_exit_4_corrupt_precedent_no_crash_todays_order_reason_printed(self):
        self.enroll()
        path = self.write_constitutional(activation="on")
        trpb.sign(path, self.operator_key)
        (self.harness / "precedents" / "PR-666.json").write_text("{not json", encoding="utf-8")
        self.set_tasks({"T-1": task(priority=1, title="only task")})
        code, out = self.run_next(agent="tester")
        self.assertEqual(code, 0)
        self.assertIn("next: T-1 ", out)
        self.assertIn("phase-b claim order not applied:", out)
        self.assertIn("dispatch exited 4", out)


class ZeroWriteAcrossTheGatedAdvisory(PhaseBAdvisoryFixture):
    """Extends AD2-54 / T-421's ZeroWritesAcrossPhaseB to the consumer side:
    `next`/`status`, run against BOTH a closed and an open gate, must leave
    every store byte-identical (no lease expired in either fixture)."""

    def _snapshot(self):
        return {str(p.relative_to(self.base)): p.read_bytes()
                for p in sorted(self.base.rglob("*")) if p.is_file()}

    def test_gate_closed_writes_nothing(self):
        self.set_tasks({"T-1": task(priority=1)})
        before = self._snapshot()
        self.run_next(agent="tester")
        self.run_status(agent="tester")
        self.assertEqual(before, self._snapshot())

    def test_gate_open_writes_nothing(self):
        self.enroll()
        path = self.write_constitutional(activation="on")
        trpb.sign(path, self.operator_key)
        self.set_tasks({"T-1": task(priority=1)})
        before = self._snapshot()
        self.run_next(agent="tester")
        self.run_status(agent="tester")
        self.assertEqual(before, self._snapshot())


if __name__ == "__main__":
    unittest.main()
