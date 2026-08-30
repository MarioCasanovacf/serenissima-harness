"""Unit tests for T-354's slice of .harness/bin/precedent.py: graded force
computed on read (A2, V1-22..V1-27), the activity-clock decay flag with its
calibrated N (A9.4, V1-28..V1-30), the `stale` validity-conditions pass
(A5, V1-34/V1-35), and the `show`/`list` v2 stdout contract (V1-43/V1-44).

Convention matches test_precedent.py/test_precedent_v2.py/
test_precedent_conflicts.py: every test invokes the real CLI via subprocess
against an isolated `--root` (a fresh TemporaryDirectory per test). NOTHING
in this file ever writes a PR-*.json record under the live
`.harness/precedents/` registry (T-354's own OWNS-EXACTLY clause forbids
it -- the live registry belongs to T-355, which may be running
concurrently).

Two fixture-construction styles are used, deliberately:

  1. Live CLI `publish` calls (LiveCLIReiterationTests, WeakeningValuation-
     LiveCLITests, NoneForceTests) -- for the reiteration/zeroing/weakening
     scenarios, where relative *ordering* of `published_at` inside the
     qualifying-applications counter (V1-23) does not matter: the counter
     sums over a set of relations sorted by (published_at, id), and
     `publish`'s own monotonic PR-NNN allocation means id order already
     matches call order even when two calls land in the same wall-clock
     second. This exercises the real CLI end-to-end for the load-bearing
     force computation.

  2. Hand-crafted raw JSON records (RawFixtureTestCase and its subclasses)
     -- for the decay clock (V1-28) and the validity-conditions pass
     (V1-34/V1-35), where the test needs EXACT control over `published_at`
     ordering (batch-mate exclusion, the N=10 boundary) or over the exact
     file-line/bare-path grammar (V1-35) that no `publish` call can produce
     directly. This is the same sanctioned pattern test_precedent_v2.py's
     `write_v1_record` and test_precedent_conflicts.py's `write_raw_record`
     already use for registry-wide-sweep fixtures that `publish` itself
     cannot mint (tampered/legacy-shaped data, exact timestamp control).
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRECEDENT_PY = ROOT / ".harness" / "bin" / "precedent.py"

# A real, permanent, tracked task file -- never a fixture this file created.
REAL_TASK_A = "T-330"


def run(*args, env=None):
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args)
    return subprocess.run(cmd, text=True, capture_output=True, env=env)


def rel(rtype, target, below_target_tier=False, **extra):
    """One relation object, schema v2 shape, matching precedent.py's own
    make_relation() output exactly."""
    r = {"type": rtype, "target": target, "distinguishing_facts": None,
         "factors": [], "factor_note": None, "controlling_authority": None,
         "target_tier_declared": None, "below_target_tier": below_target_tier}
    r.update(extra)
    return r


def base_record(pr_id, **overrides):
    """A complete, schema_version-2-shaped record with every field a live
    `publish` would write. Callers override only what a given test cares
    about (status, authority_tier, relations, published_by, published_at,
    cited_by, operation, validity_conditions, ...)."""
    rec = {
        "id": pr_id, "schema_version": 2, "title": "t", "subject": "subj-" + pr_id.lower(),
        "status": "active", "authority_tier": 3, "tier_evidence": [REAL_TASK_A],
        "ratio": "r", "dicta": [], "scope_conditions": ["role:worker"],
        "declared_width": "narrow", "revisit_trigger": "revisit",
        "confirmation_status": "unconfirmed", "confirmed_by": None, "confirmed_at": None,
        "narrowed_scope": None, "confirmation_note": None,
        "relations": [], "cites": [], "cited_by": [],
        "overruled_by": None, "superseded_by": None, "voided_by": None,
        "issuing_task": REAL_TASK_A, "published_by": "author-" + pr_id.lower(),
        "published_at": "2026-01-01T00:00:00Z",
        "sources": [REAL_TASK_A], "validity_conditions": ["a free-text validity condition"],
        "operation": {"type": "determination", "subtype": None},
        "interpretive_code_version": "v1",
    }
    rec.update(overrides)
    return rec


class RawFixtureTestCase(unittest.TestCase):
    """Base class for hand-crafted-record tests: isolated registry root,
    a `write()` helper, byte-level snapshot helpers for the read-only
    proof (`stale` must leave the registry byte-identical)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "registry"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rec):
        (self.root / (rec["id"] + ".json")).write_text(
            json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        return rec

    def load(self, pr_id):
        return json.loads((self.root / (pr_id + ".json")).read_text(encoding="utf-8"))

    def snapshot(self):
        """Every file's exact bytes, keyed by name -- includes any
        events.jsonl sidecar that a (would-be) side effect might create."""
        return {p.name: p.read_bytes() for p in sorted(self.root.iterdir()) if p.is_file()}

    def show(self, pr_id):
        return run("show", pr_id, "--root", str(self.root))

    def list_json(self):
        return run("list", "--root", str(self.root), "--json")

    def stale(self, json_mode=False):
        args = ["stale", "--root", str(self.root)]
        if json_mode:
            args.append("--json")
        return run(*args)


# ==========================================================================
# A. Reiteration -- the qualifying-applications counter C (V1-23), via the
#    LIVE CLI end to end. Mandatory per board T-354 AC-3: "assert the
#    computed force level at N-1, at N and at N+1."
# ==========================================================================

class LiveCLIReiterationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "registry"

    def tearDown(self):
        self._tmp.cleanup()

    def publish(self, agent, task, subject, tier=3, extra_args=None):
        args = ["publish", "--root", str(self.root), "--agent", agent, "--task", task,
                "--title", "t", "--subject", subject, "--tier", str(tier),
                "--tier-evidence", REAL_TASK_A, "--ratio", "r", "--width", "narrow",
                "--sources", REAL_TASK_A, "--code-version", "v1"]
        if tier in (1, 2, 3):
            args += ["--scope", "role:worker", "--revisit-trigger", "revisit",
                      "--validity", "a validity condition"]
        if not (extra_args and any(a == "--case" for a in extra_args)):
            hroot = pathlib.Path(self.root).parent
            cdir = hroot / "cases"
            cdir.mkdir(parents=True, exist_ok=True)
            existing = [int(p.stem[2:]) for p in cdir.glob("C-*.json") if p.stem[2:].isdigit()]
            cnum = max(existing) + 1 if existing else 1
            cid = "C-{:03d}".format(cnum)
            cdata = {
                "id": cid, "question": "case for {}".format(task), "task": task,
                "opened_by": agent, "ts": "2026-08-24T00:00:00Z",
                "status": "open", "disposal": None
            }
            (cdir / "{}.json".format(cid)).write_text(json.dumps(cdata, indent=2) + "\n", encoding="utf-8")
            args += ["--case", cid]
        if extra_args:
            args += extra_args
        return run(*args)

    def publish_ok(self, *a, **kw):
        result = self.publish(*a, **kw)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip().splitlines()[-1].split()[-1]

    def show(self, pr_id):
        return run("show", pr_id, "--root", str(self.root))

    def load(self, pr_id):
        return json.loads((self.root / (pr_id + ".json")).read_text(encoding="utf-8"))

    def overrule_embedding_args(self, target_id):
        """T-370 amendment (PR-019, A.3.1): every successful `--overrules`
        call now must embed the overruled record's ratio verbatim plus its
        authorship (record id, published_by, issuing task) or the publish
        is refused. Reads the target's own on-disk fields so the required
        byte-exact ratio match holds -- see the amended-assertion list in
        this task's handoff."""
        target = self.load(target_id)
        ratio_file = pathlib.Path(self._tmp.name) / (target_id + "-overruled-ratio.txt")
        ratio_file.write_text(target["ratio"], encoding="utf-8")
        return ["--overruled-ratio-file", str(ratio_file),
                "--overruled-record-id", target_id,
                "--overruled-published-by", target["published_by"],
                "--overruled-issuing-task", target["issuing_task"]]

    def test_reiteration_threshold_at_n_minus_1_n_and_n_plus_1(self):
        """The board's mandatory reiteration test: N=3 (V1-22's disclosed
        R-2 threshold). Build up 2, 3, 4 qualifying `follows` applications
        from DIFFERENT agents (no self-reiteration, V1-23) at the SAME tier
        as the target (so below_target_tier is False, S-02) and assert the
        computed force level at each point."""
        target = self.publish_ok("author-x", "T-600", "target-subj", tier=3)

        self.publish_ok("peer-1", "T-601", "app-1", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("force: binding", result.stdout)
        self.assertNotIn("consistent applications", result.stdout)

        # N-1 = 2
        self.publish_ok("peer-2", "T-602", "app-2", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: binding", result.stdout)

        # N = 3
        self.publish_ok("peer-3", "T-603", "app-3", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: settled (consistent applications: 3)", result.stdout)

        # N+1 = 4
        self.publish_ok("peer-4", "T-604", "app-4", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: settled (consistent applications: 4)", result.stdout)

    def test_below_target_tier_application_never_counts(self):
        """S-02: a lower-authority (higher tier number) follower's `follows`
        is persuasive only for its own author -- it must NOT raise the
        target's force."""
        target = self.publish_ok("author-hi", "T-610", "target-hi", tier=1)
        self.publish_ok("peer-lo", "T-611", "app-lo", tier=4, extra_args=["--follows", target])
        result = self.show(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("force: binding", result.stdout)
        self.assertNotIn("consistent applications", result.stdout)

    def test_self_reiteration_never_counts(self):
        """V1-23: `R.published_by != X.published_by` -- an author cannot
        raise their own record's force by publishing a second record that
        follows it."""
        target = self.publish_ok("same-agent", "T-620", "target-self", tier=3)
        self.publish_ok("same-agent", "T-621", "app-self", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: binding", result.stdout)
        self.assertNotIn("consistent applications", result.stdout)

    def test_declarative_reinterprets_increments_like_follows(self):
        """V1-23: a `reinterprets` relation with operation.subtype
        'declarative' is a consistent application (applying the ratio to a
        new case), incrementing C exactly like `follows`."""
        target = self.publish_ok("author-y", "T-630", "target-decl", tier=3)
        self.publish_ok("peer-a", "T-631", "app-decl-a", tier=3,
                         extra_args=["--reinterprets", target,
                                     "--operation", "reinterpretation",
                                     "--operation-subtype", "declarative"])
        self.publish_ok("peer-b", "T-632", "app-decl-b", tier=3,
                         extra_args=["--reinterprets", target,
                                     "--operation", "reinterpretation",
                                     "--operation-subtype", "declarative"])
        self.publish_ok("peer-c", "T-633", "app-decl-c", tier=3,
                         extra_args=["--reinterprets", target,
                                     "--operation", "reinterpretation",
                                     "--operation-subtype", "declarative"])
        result = self.show(target)
        self.assertIn("force: settled (consistent applications: 3)", result.stdout)

    def test_distinguishes_zeroes_the_counter(self):
        """R-3, carried: a recognized contrary application ZEROES the
        counter, it never merely skips an increment."""
        target = self.publish_ok("author-z", "T-640", "target-zero", tier=3)
        self.publish_ok("peer-1", "T-641", "app-zero-1", tier=3, extra_args=["--follows", target])
        self.publish_ok("peer-2", "T-642", "app-zero-2", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: binding", result.stdout)  # C=2, pre-zero

        self.publish_ok("peer-3", "T-643", "app-zero-3", tier=3,
                         extra_args=["--distinguishes", target,
                                     "--distinguishing-facts", "some material fact differs"])
        result = self.show(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("force: binding", result.stdout)
        self.assertNotIn("consistent applications", result.stdout)  # C reset to 0

    def test_corrective_reinterprets_zeroes_the_counter(self):
        """R-3, carried, via the OTHER zeroing route named in V1-23's
        pseudocode: a corrective (restrictive/extensive) `reinterprets`
        zeroes C exactly like `distinguishes`."""
        target = self.publish_ok("author-w", "T-650", "target-zero2", tier=3)
        self.publish_ok("peer-1", "T-651", "app-zero2-1", tier=3, extra_args=["--follows", target])
        self.publish_ok("peer-2", "T-652", "app-zero2-2", tier=3, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: binding", result.stdout)

        self.publish_ok("peer-3", "T-653", "app-zero2-3", tier=3,
                         extra_args=["--reinterprets", target,
                                     "--operation", "reinterpretation",
                                     "--operation-subtype", "corrective-restrictive",
                                     "--sources", "T-344"])
        result = self.show(target)
        self.assertNotIn("consistent applications", result.stdout)

    def test_tier4_reiterated_at_c_ge_3(self):
        """V1-22 table: tier-4, active, C>=3 -> 'reiterated' (never
        'settled' -- that level is reserved for tiers 1-3)."""
        target = self.publish_ok("author-t4", "T-660", "target-t4", tier=4)
        for i, agent in enumerate(("peer-t4-1", "peer-t4-2")):
            self.publish_ok(agent, "T-66{}".format(i + 1), "app-t4-{}".format(i), tier=4,
                             extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: persuasive", result.stdout)
        self.assertNotIn("reiterated", result.stdout)

        self.publish_ok("peer-t4-3", "T-664", "app-t4-3", tier=4, extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: reiterated (consistent applications: 3)", result.stdout)

    def test_force_none_when_target_overruled(self):
        """V1-22 table: status != active -> force 'none', with the
        '(status: <status>)' suffix (V1-43).

        T-370 AMENDMENT (PR-019, A.3.1), disclosed as a DEVIATION beyond
        this task's named three-file amendment licence (test_precedent.py/
        test_precedent_v2.py/test_precedent_conflicts.py): this file is not
        in that licence, but the displacement-bridge enforcement correctly
        refuses this call's --overrules exactly as it does everywhere else,
        so the fix is the identical mechanical one -- embed the overruled
        record's ratio verbatim plus its authorship. See this task's
        handoff for the full reasoning."""
        target = self.publish_ok("author-ov", "T-670", "target-ov", tier=1)
        self.publish_ok("peer-1", "T-671", "app-ov-1", tier=3, extra_args=["--follows", target])
        result = self.publish("overruler", "T-672", "overrule-ov", tier=1,
                               extra_args=["--overrules", target, "--factor", "doctrinal_change",
                                           "--factor-note", "note", "--acknowledge-reliance"]
                               + self.overrule_embedding_args(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.show(target)
        self.assertIn("force: none (status: overruled)", result.stdout)

    def test_weakening_valuation_renders_persuasive_despite_high_c(self):
        """V1-24: an effective weakening valuation (error-in-pronouncement
        or context-change, below_target_tier False) renders a tier 1-3
        target's force 'persuasive' INSTEAD OF binding/settled, regardless
        of C."""
        target = self.publish_ok("author-wk", "T-680", "target-weak", tier=3)
        for i, agent in enumerate(("peer-wk-1", "peer-wk-2", "peer-wk-3")):
            self.publish_ok(agent, "T-68{}".format(i + 1), "app-wk-{}".format(i), tier=3,
                             extra_args=["--follows", target])
        result = self.show(target)
        self.assertIn("force: settled (consistent applications: 3)", result.stdout)

        result = self.publish("valuator", "T-684", "valuation-weak", tier=3,
                               extra_args=["--operation", "valuation",
                                           "--operation-subtype", "context-change",
                                           "--revalues", target,
                                           "--valuation-note", "context changed"])
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.show(target)
        self.assertIn("force: persuasive", result.stdout)
        self.assertNotIn("force: settled", result.stdout)
        self.assertIn("weakened_by:", result.stdout)
        self.assertIn("(valuation/context-change)", result.stdout)

    def test_obiter_valuation_has_no_force_effect(self):
        """V1-24: subtype 'obiter' has no whole-record force effect (it
        reclassifies a passage, not the ratio's force)."""
        target = self.publish_ok("author-ob", "T-690", "target-obiter", tier=3)
        result = self.publish("valuator-ob", "T-691", "valuation-obiter", tier=3,
                               extra_args=["--operation", "valuation",
                                           "--operation-subtype", "obiter",
                                           "--revalues", target,
                                           "--valuation-note", "this passage is obiter"])
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.show(target)
        self.assertIn("force: binding", result.stdout)
        self.assertNotIn("weakened_by:", result.stdout)

    def test_below_target_tier_valuation_has_no_force_effect(self):
        """V1-24: a below-target-tier valuation is recorded and rendered on
        the VALUATION record but has NO effect on the target's force (the
        S-02 persuasive-only-for-its-author analogue)."""
        target = self.publish_ok("author-btv", "T-700", "target-btv", tier=1)
        result = self.publish("valuator-lo", "T-701", "valuation-btv", tier=4,
                               extra_args=["--operation", "valuation",
                                           "--operation-subtype", "context-change",
                                           "--revalues", target,
                                           "--valuation-note", "context changed"])
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.show(target)
        self.assertIn("force: binding", result.stdout)
        self.assertNotIn("weakened_by:", result.stdout)


# ==========================================================================
# B. Decay -- the activity clock (A9.4, V1-28/V1-29), via hand-crafted
#    records for exact `published_at` control. Mandatory per board T-354
#    AC-4: prove the NEGATIVE -- a decayed record is flagged but its
#    `status` field is unchanged.
# ==========================================================================

class DecayTests(RawFixtureTestCase):
    def _seed_with_subsequent_publications(self, target, count):
        self.write(target)
        for i in range(count):
            self.write(base_record(
                "PR-{:03d}".format(i + 2), authority_tier=4,
                published_by="filler-{}".format(i),
                published_at="2026-02-01T00:00:{:02d}Z".format(i % 60)))

    def test_decay_candidate_flagged_status_unchanged(self):
        """The board's mandatory negative proof: a decayed record is
        FLAGGED as a reconsideration candidate and its `status` field is
        UNCHANGED (still 'active') -- auto-expiry is forbidden (A2;
        addendum sec.6)."""
        target = base_record("PR-001", authority_tier=2, cited_by=[],
                              published_at="2026-01-01T00:00:00Z")
        self._seed_with_subsequent_publications(target, 10)  # clock == DECAY_N

        before = self.load("PR-001")
        self.assertEqual(before["status"], "active")

        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("STALE check=D [decay-candidate] PR-001: cited_by empty after "
                      "10 subsequent publications (threshold 10)", result.stdout)

        after = self.load("PR-001")
        self.assertEqual(after["status"], "active",
                          "stale must NEVER auto-expire or otherwise mutate status")
        self.assertEqual(before, after, "stale must mutate NOTHING on the flagged record")

        show_result = self.show("PR-001")
        self.assertIn("RECONSIDERATION CANDIDATE", show_result.stdout)
        self.assertIn("threshold 10", show_result.stdout)

    def test_clock_of_9_is_not_yet_a_candidate(self):
        """The N=10 boundary (V1-29), the other side: 9 subsequent
        publications is NOT enough."""
        target = base_record("PR-001", authority_tier=2, cited_by=[],
                              published_at="2026-01-01T00:00:00Z")
        self._seed_with_subsequent_publications(target, 9)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("decay-candidate", result.stdout)
        show_result = self.show("PR-001")
        self.assertIn("decay: none", show_result.stdout)

    def test_tier4_never_decay_flagged_even_at_huge_clock(self):
        """R-16: tier 4 is a legitimate permanent persuasive mode -- NEVER
        decay-flagged, no matter how large the clock."""
        target = base_record("PR-001", authority_tier=4, cited_by=[],
                              published_at="2026-01-01T00:00:00Z")
        self._seed_with_subsequent_publications(target, 20)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_nonempty_cited_by_never_decay_flagged(self):
        """V1-29: `cited_by` non-empty means SOME later record has cited or
        related to this one -- not neglect, never a candidate regardless
        of clock."""
        target = base_record("PR-001", authority_tier=2, cited_by=["PR-999"],
                              published_at="2026-01-01T00:00:00Z")
        self._seed_with_subsequent_publications(target, 15)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_non_active_record_never_decay_flagged(self):
        """V1-29 implicitly, V1-22 explicitly: a dead record has no force
        and is not a reconsideration candidate -- decay is about neglect of
        a LIVE ratio."""
        target = base_record("PR-001", authority_tier=2, status="overruled",
                              cited_by=[], published_at="2026-01-01T00:00:00Z")
        self._seed_with_subsequent_publications(target, 15)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_batch_mates_excluded_from_the_clock(self):
        """V1-28: records sharing X's EXACT `published_at` never count
        toward its clock -- ten batch-mates at the identical timestamp
        must NOT trip the threshold."""
        target = base_record("PR-001", authority_tier=2, cited_by=[],
                              published_at="2026-03-01T00:00:00Z")
        self.write(target)
        for i in range(10):
            self.write(base_record("PR-{:03d}".format(i + 2), authority_tier=4,
                                    published_by="batchmate-{}".format(i),
                                    published_at="2026-03-01T00:00:00Z"))  # identical ts
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        show_result = self.show("PR-001")
        self.assertIn("decay: none", show_result.stdout)


# ==========================================================================
# C. The validity-conditions staleness pass (A5, V1-34/V1-35)
# ==========================================================================

class ValidityConditionsCheckTests(RawFixtureTestCase):
    def test_file_line_entry_passes_when_file_and_line_count_ok(self):
        rec = base_record("PR-001", validity_conditions=[".harness/bin/harness_common.py:1"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_file_line_entry_fails_on_missing_file(self):
        rec = base_record("PR-001",
                           validity_conditions=["does/not/exist/at/all.py:1"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("STALE check=V [validity-condition-failed] PR-001: "
                      "'does/not/exist/at/all.py:1' -- file does not exist", result.stdout)

    def test_file_line_entry_fails_when_upper_bound_exceeds_line_count(self):
        rec = base_record("PR-001",
                           validity_conditions=[".harness/bin/harness_common.py:999999999"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("STALE check=V [validity-condition-failed] PR-001:", result.stdout)
        self.assertIn("fewer than the declared upper bound 999999999", result.stdout)

    def test_bare_path_entry_passes_when_path_exists(self):
        rec = base_record("PR-001", validity_conditions=["path:.harness/bin"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bare_path_entry_fails_when_path_missing(self):
        rec = base_record("PR-001", validity_conditions=["path:.harness/bin/does-not-exist-xyz.py"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("'path:.harness/bin/does-not-exist-xyz.py' -- path does not exist",
                      result.stdout)

    def test_unchecked_free_text_entry_never_flagged(self):
        """V1-35: any entry not matching the file-line or bare-path grammar
        is free text -- unchecked, NEVER flagged, even when obviously
        false ('the moon is made of cheese')."""
        rec = base_record("PR-001",
                           validity_conditions=["the moon is made of cheese"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_only_active_records_are_checked(self):
        """V1-34: check V runs 'per ACTIVE record' -- a non-active record's
        failing validity_conditions is never a finding."""
        rec = base_record("PR-001", status="overruled",
                           validity_conditions=["does/not/exist.py:1"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v1_record_has_no_validity_conditions_never_a_finding(self):
        """V1-36 dual-read: a schema_version-1 record has no
        `validity_conditions` key -- check V skips it entirely (never a
        finding, never an error)."""
        rec = base_record("PR-001", schema_version=1)
        del rec["sources"]
        del rec["validity_conditions"]
        del rec["operation"]
        del rec["interpretive_code_version"]
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_multiple_failing_entries_produce_multiple_finding_lines(self):
        rec = base_record("PR-001", validity_conditions=[
            "does/not/exist/a.py:1", "does/not/exist/b.py:1"])
        self.write(rec)
        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("STALE check=V"), 2)
        self.assertIn("2 reconsideration candidate(s) across 1 record(s)", result.stdout)

    def test_json_mode_reports_unchecked_free_text_entries(self):
        """V1-35, exact words: a free-text validity_conditions entry is
        "reported by `stale --json` as `\"unchecked\": true`, never
        flagged, never an error" -- present in the --json array, but never
        counted toward the exit code or the text-mode K/R summary."""
        rec = base_record("PR-001", validity_conditions=[
            "the moon is made of cheese", "does/not/exist.py:1"])
        self.write(rec)

        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)  # the checkable failure only
        self.assertEqual(result.stdout.count("STALE check=V"), 1)
        self.assertIn("1 reconsideration candidate(s) across 1 record(s)", result.stdout)
        self.assertNotIn("cheese", result.stdout)  # never rendered in text mode

        result = self.stale(json_mode=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload), 2)
        failing = [e for e in payload if e.get("name") == "validity-condition-failed"]
        unchecked = [e for e in payload if e.get("unchecked") is True]
        self.assertEqual(len(failing), 1)
        self.assertEqual(len(unchecked), 1)
        self.assertEqual(unchecked[0]["record"], "PR-001")
        self.assertEqual(unchecked[0]["entry"], "the moon is made of cheese")

    def test_json_mode_unchecked_entries_never_appear_for_non_active_records(self):
        rec = base_record("PR-001", status="overruled",
                           validity_conditions=["free text, never checked"])
        self.write(rec)
        result = self.stale(json_mode=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload, [])


# ==========================================================================
# D. `stale` is read-only: mutates nothing, logs no event (board T-354
#    AC-5). Mandatory per the board: byte-identical registry before/after.
# ==========================================================================

class StaleReadOnlyTests(RawFixtureTestCase):
    def test_registry_byte_identical_before_and_after_a_run_with_findings(self):
        self.write(base_record("PR-001", authority_tier=2, cited_by=[],
                                validity_conditions=["does/not/exist.py:1"]))
        self.write(base_record("PR-002", authority_tier=3))
        before = self.snapshot()

        result = self.stale()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)  # a run WITH findings

        after = self.snapshot()
        self.assertEqual(before, after,
                          "stale must leave the registry byte-identical -- it is a read verb "
                          "in the full cite/conflicts sense (SDR-23)")

    def test_no_sidecar_events_file_created(self):
        """DECISION (module docstring): stale logs no event at all, unlike
        every writing verb which routes through emit_event(). No
        <root>/events.jsonl sidecar should exist after a run."""
        self.write(base_record("PR-001"))
        self.assertFalse((self.root / "events.jsonl").exists())
        self.stale()
        self.assertFalse((self.root / "events.jsonl").exists())

    def test_exit_0_when_clean(self):
        self.write(base_record("PR-001", authority_tier=2, cited_by=["PR-999"]))
        result = self.stale()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stale: 0 reconsideration candidate(s) across 1 record(s)", result.stdout)

    def test_json_mode_shape(self):
        self.write(base_record("PR-001", validity_conditions=["does/not/exist.py:1"]))
        result = self.stale(json_mode=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["check"], "V")
        self.assertEqual(payload[0]["record"], "PR-001")


# ==========================================================================
# E. `show`/`list` v2 stdout rendering (V1-43/V1-44) -- dual-read and the
#    schema-v2 case together.
# ==========================================================================

class RenderingTests(RawFixtureTestCase):
    def test_show_renders_all_four_v2_lines_for_a_v2_record(self):
        self.write(base_record("PR-001", operation={"type": "determination", "subtype": None},
                                interpretive_code_version="v3"))
        result = self.show("PR-001")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("force: binding", result.stdout)
        self.assertIn("decay: none", result.stdout)
        self.assertIn("operation: determination", result.stdout)
        self.assertIn("interpretive_code_version: v3", result.stdout)

    def test_show_renders_subtype_when_present(self):
        target = self.write(base_record("PR-001"))
        self.write(base_record(
            "PR-002", authority_tier=3, published_by="reinterpreter",
            operation={"type": "reinterpretation", "subtype": "declarative"},
            relations=[rel("reinterprets", "PR-001")]))
        result = self.show("PR-002")
        self.assertIn("operation: reinterpretation/declarative", result.stdout)

    def test_show_dual_read_v1_operation_and_code_version_lines(self):
        rec = base_record("PR-001", schema_version=1)
        del rec["sources"]
        del rec["validity_conditions"]
        del rec["operation"]
        del rec["interpretive_code_version"]
        self.write(rec)
        result = self.show("PR-001")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("operation: determination (implied, schema v1)", result.stdout)
        self.assertIn("interpretive_code_version: (none, schema v1)", result.stdout)
        self.assertIn("force: binding", result.stdout)
        self.assertIn("decay: none", result.stdout)

    def test_list_text_mode_carries_force_column(self):
        self.write(base_record("PR-001", authority_tier=2))
        result = run("list", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FORCE", result.stdout)
        self.assertIn("force=binding", result.stdout)

    def test_list_json_mode_carries_v2_keys(self):
        self.write(base_record("PR-001", authority_tier=2, cited_by=[]))
        result = self.list_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload), 1)
        entry = payload[0]
        self.assertEqual(entry["force"], "binding")
        self.assertIn("decay_candidate", entry)
        self.assertFalse(entry["decay_candidate"])
        self.assertEqual(entry["operation"], {"type": "determination", "subtype": None})
        self.assertEqual(entry["interpretive_code_version"], "v1")

    def test_list_json_mode_dual_read_operation_default(self):
        rec = base_record("PR-001", schema_version=1)
        del rec["sources"]
        del rec["validity_conditions"]
        del rec["operation"]
        del rec["interpretive_code_version"]
        self.write(rec)
        result = self.list_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload[0]["operation"], {"type": "determination", "subtype": None})
        self.assertIsNone(payload[0]["interpretive_code_version"])

    def test_list_json_mode_carries_decay_candidate_true(self):
        target = base_record("PR-001", authority_tier=2, cited_by=[],
                              published_at="2026-01-01T00:00:00Z")
        self.write(target)
        for i in range(10):
            self.write(base_record("PR-{:03d}".format(i + 2), authority_tier=4,
                                    published_by="filler-{}".format(i),
                                    published_at="2026-02-01T00:00:00Z"))
        result = self.list_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        target_entry = next(e for e in payload if e["id"] == "PR-001")
        self.assertTrue(target_entry["decay_candidate"])

    def test_force_and_decay_computed_over_whole_root_even_when_filtered_out(self):
        """V1-27: force/decay are computed over the SAME root's records,
        not just the filtered view -- a tier filter must not change the
        computed force of the records that DO match."""
        target = base_record("PR-001", authority_tier=1, published_by="author-filter")
        self.write(target)
        for i, agent in enumerate(("peer-f1", "peer-f2", "peer-f3")):
            self.write(base_record("PR-{:03d}".format(i + 2), authority_tier=1,
                                    published_by=agent,
                                    relations=[rel("follows", "PR-001")]))
        result = run("list", "--root", str(self.root), "--json", "--tier", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        target_entry = next(e for e in payload if e["id"] == "PR-001")
        self.assertEqual(target_entry["force"], "settled")


if __name__ == "__main__":
    unittest.main()
