"""Unit tests for the four T-343 seed precedent records (PR-001..PR-004),
published into the LIVE `.harness/precedents/` registry via the real
`precedent.py publish` CLI (never hand-written -- T-343 AC-1).

READ-ONLY against the live registry (T-343 AC-5): every assertion here uses
`precedent.py cite`/`show`/`list` (subprocess, matching test_precedent.py's
own convention) or plain file reads of already-published records; nothing
here calls `publish`/`confirm`, so running this suite never mutates
`.harness/precedents/` (checked explicitly by
NoMutationGuaranteeTests below, mirroring test_precedent_conflicts.py's own
before/after-snapshot convention for the same property).

Ratio/dicta quotation fidelity (T-343 AC-2/AC-5): this file re-reads
ORCHESTRATION.md at run time and re-slices the exact line ranges T-343's own
acceptance criteria name (P-023 :58-67, P-025 :82-90, P-026 :211-218,
F6 :119-126), then asserts each record's `ratio` (and its source-derived
`dicta` entry) are contained in a whitespace-normalized join of that
range -- "read ORCHESTRATION.md and compare, do not trust the record."
Normalizing whitespace only collapses the source's editorial line-wrap
(a wrapped sentence has a newline where prose has a space); it never lets a
paraphrase pass, because every word and punctuation mark must still match.

Citation resolution (T-343 AC-5, "every citation resolves"): read together
with SDR-12 (`docs/precedent-research/synthesis-design-requirements.md`),
which requires the OPPOSITE for exactly one token on exactly one record --
"T-343's P-023 seed must RECORD the live integrity gap ... a publish that
refuses dangling evidence could never record the very defect the layer
exists to catch." PR-001 (the P-023 seed) therefore cites the token "P-023"
deliberately, and it does not resolve (verified live: P-023 is absent from
`state.json evolution.accepted_mutations` -- that absence is the gap this
whole layer exists to catch). This suite asserts full citation resolution
for PR-002/PR-003/PR-004 and, for PR-001, asserts every OTHER citation
resolves while "P-023" is the one and only dangling reference -- named and
verified, never silently skipped.
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRECEDENT_PY = ROOT / ".harness" / "bin" / "precedent.py"
LIVE_REGISTRY = ROOT / ".harness" / "precedents"
ORCHESTRATION = ROOT / "ORCHESTRATION.md"

# Load precedent.py as a module so schema checks reuse ITS OWN vocabulary
# (VALID_TIERS/VALID_STATUS/VALID_WIDTH, SUBJECT_RE, tier_evidence_kind_ok,
# resolve_citation) rather than re-implementing the citation grammar or the
# tier-evidence table redundantly (C-2, non-additive duplication risk).
# Read-only: only module-level constants/functions are used, nothing here
# calls any of precedent.py's mutating verbs directly. precedent.py does
# `import harness_common as hc` as a bare sibling import (true when run as a
# script, where Python puts its own directory on sys.path[0]); replicate
# that here since importlib.util does not do it for us.
if str(PRECEDENT_PY.parent) not in sys.path:
    sys.path.insert(0, str(PRECEDENT_PY.parent))
_spec = importlib.util.spec_from_file_location("precedent_under_test", str(PRECEDENT_PY))
precedent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(precedent)


def run(*args):
    """Invoke the real CLI against the LIVE registry explicitly (--root
    pinned) so an ambient PRECEDENT_ROOT env var can never silently redirect
    a "read the live registry" test at something else."""
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args) + ["--root", str(LIVE_REGISTRY)]
    return subprocess.run(cmd, text=True, capture_output=True)


def load_record(pr_id):
    return json.loads((LIVE_REGISTRY / (pr_id + ".json")).read_text(encoding="utf-8"))


def source_block(a, b):
    lines = ORCHESTRATION.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[a - 1:b])


def norm(text):
    """Collapse all whitespace runs (including the source's editorial line
    wraps) to single spaces, so a wrapped sentence compares equal to itself
    unwrapped -- without permitting any word/punctuation substitution."""
    return " ".join(text.split())


SEED_IDS = ("PR-001", "PR-002", "PR-003", "PR-004")

# The exact source ranges named by T-343's own acceptance criteria for each
# record's quoted ratio.
SOURCE_RANGES = {
    "PR-001": (58, 67),    # P-023, terminal-state reopen
    "PR-002": (82, 90),    # P-025, test-discovery precision
    "PR-003": (211, 218),  # P-026, verbatim promotion
    "PR-004": (119, 126),  # F6, verifier rotation
}
EXPECTED_TIER = {"PR-001": 3, "PR-002": 2, "PR-003": 2, "PR-004": 3}
EXPECTED_SUBJECT = {
    "PR-001": "reopen-terminal-state",
    "PR-002": "test-discovery-precision",
    "PR-003": "verbatim-promotion",
    "PR-004": "verifier-rotation",
}
EXPECTED_ISSUING_TASK = {
    "PR-001": "T-302",  # producer(worker-b) != approver(verifier-b) verdict, tier-3 evidence
    "PR-002": "T-057",  # ORCHESTRATION.md doc change implementing P-025, verdicted done
    "PR-003": "T-057",  # same task, P-026's doc change
    "PR-004": "T-031",  # rotated verifier-b verdict, F6's own founding precedent
}


class LiveRegistryPresenceTests(unittest.TestCase):
    """Exactly the four seed records exist, minted by `publish` (real IDs)."""

    def test_exactly_four_seed_records_present(self):
        ids = sorted(p.stem for p in LIVE_REGISTRY.glob("PR-*.json"))
        self.assertEqual(ids, list(SEED_IDS),
                          "expected exactly the four T-343 seed records under "
                          ".harness/precedents/, found {}".format(ids))


class SchemaValidationTests(unittest.TestCase):
    """Each record loads and validates against the SDR-17 field table."""

    def _check_common_schema(self, pr_id, rec):
        self.assertEqual(rec.get("id"), pr_id)
        self.assertEqual(rec.get("schema_version"), precedent.SCHEMA_VERSION)
        self.assertIn(rec.get("authority_tier"), precedent.VALID_TIERS)
        self.assertIn(rec.get("status"), precedent.VALID_STATUS)
        self.assertEqual(rec.get("status"), "active")
        self.assertIn(rec.get("declared_width"), precedent.VALID_WIDTH)
        self.assertTrue(precedent.SUBJECT_RE.match(rec.get("subject") or ""),
                         "subject {!r} fails the slug regex ^[a-z0-9-]+$".format(rec.get("subject")))
        self.assertLessEqual(len(rec.get("title", "")), 80, "title exceeds 80 chars (SDR-17.2)")
        self.assertTrue((rec.get("ratio") or "").strip(), "ratio must be non-empty (SDR-17.1)")
        self.assertIsInstance(rec.get("dicta"), list)
        self.assertIsInstance(rec.get("tier_evidence"), list)
        self.assertTrue(rec["tier_evidence"], "tier_evidence must be non-empty (SDR-17.3)")
        self.assertTrue(
            precedent.tier_evidence_kind_ok(rec["authority_tier"], rec["tier_evidence"]),
            "tier_evidence {} lacks the token kind the section-3 table requires for tier {}"
            .format(rec["tier_evidence"], rec["authority_tier"]))
        if rec["authority_tier"] in (1, 2, 3):
            self.assertTrue(rec.get("scope_conditions"),
                             "scope_conditions required non-empty at tiers 1-3 (SDR-17.4)")
            self.assertTrue((rec.get("revisit_trigger") or "").strip(),
                             "revisit_trigger required non-empty at tiers 1-3 (SDR-17.4)")
        self.assertTrue(precedent.T_RE.match(rec.get("issuing_task") or ""),
                         "issuing_task {!r} must be a T-NNN token".format(rec.get("issuing_task")))
        self.assertTrue(rec.get("published_by"))
        self.assertTrue(rec.get("published_at"))
        self.assertEqual(rec.get("relations"), [])
        self.assertEqual(rec.get("cited_by"), [])
        self.assertIsNone(rec.get("overruled_by"))
        self.assertIsNone(rec.get("superseded_by"))
        self.assertIsNone(rec.get("voided_by"))

    def test_all_four_records_load_and_validate(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self._check_common_schema(pr_id, rec)
                self.assertEqual(rec["authority_tier"], EXPECTED_TIER[pr_id])
                self.assertEqual(rec["subject"], EXPECTED_SUBJECT[pr_id])
                self.assertEqual(rec["issuing_task"], EXPECTED_ISSUING_TASK[pr_id])


class ConfirmationUnconfirmedTests(unittest.TestCase):
    """SDR-17 item 15 / SDR-02: scope claims never pre-confirmed by the
    publishing author; the unconfirmed state is mechanical, not prose."""

    def test_all_four_are_unconfirmed_at_publication(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertEqual(rec.get("confirmation_status"), "unconfirmed")
                self.assertIsNone(rec.get("confirmed_by"))
                self.assertIsNone(rec.get("confirmed_at"))
                self.assertIsNone(rec.get("narrowed_scope"))
                self.assertIsNone(rec.get("confirmation_note"))


class RatioQuotationFidelityTests(unittest.TestCase):
    """AC-2/AC-5: ratio (and the source-derived dicta entry) is QUOTED
    verbatim from the cited ORCHESTRATION.md range, never paraphrased.
    Re-reads the source fresh each run; does not trust the record's claim."""

    def test_ratio_is_verbatim_substring_of_cited_source_range(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                a, b = SOURCE_RANGES[pr_id]
                source = norm(source_block(a, b))
                ratio = norm(rec["ratio"])
                self.assertTrue(ratio, "ratio must be non-empty")
                self.assertIn(ratio, source,
                              "{}'s ratio is not a verbatim (whitespace-normalized) "
                              "substring of ORCHESTRATION.md:{}-{}".format(pr_id, a, b))

    def test_source_derived_dicta_is_verbatim_substring_of_cited_source_range(self):
        # PR-001 carries a SECOND dicta entry (the integrity-gap note) that is
        # original commentary about live registry state, not a source
        # quotation -- only its first dicta entry is drawn from
        # ORCHESTRATION.md, matching the other three records' sole entry.
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                a, b = SOURCE_RANGES[pr_id]
                source = norm(source_block(a, b))
                self.assertTrue(rec["dicta"], "{} must carry >=1 dicta entry".format(pr_id))
                source_derived = rec["dicta"][0]
                self.assertIn(norm(source_derived), source,
                              "{}'s first dicta entry is not a verbatim substring of "
                              "ORCHESTRATION.md:{}-{}".format(pr_id, a, b))

    def test_ratio_and_dicta_are_actually_separated_not_the_whole_block(self):
        # Guards against dumping the entire cited block into `ratio` (which
        # would still pass the substring check above) -- AC-2 requires dicta
        # SEPARATED from ratio, so ratio must be a proper, smaller piece.
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                a, b = SOURCE_RANGES[pr_id]
                source = norm(source_block(a, b))
                self.assertLess(len(norm(rec["ratio"])), len(source),
                                 "{}'s ratio swallows the entire cited block; dicta must be "
                                 "separated out, not merged into ratio".format(pr_id))

    def test_p023_gap_and_resolution_path_are_recorded_in_the_record(self):
        # T-343 AC-3: the integrity gap and its resolution PATH must be
        # recorded INSIDE the precedent record, not merely asserted in a
        # task note. Checked against the live PR-001 record's own text.
        rec = load_record("PR-001")
        blob = json.dumps(rec)
        self.assertIn("accepted_mutations", blob, "PR-001 must name the missing ledger entry")
        self.assertIn(".harness/bin/blackboard.py:470", blob, "PR-001 must cite the code location")
        self.assertIn("ORCHESTRATION.md:58", blob, "PR-001 must cite the prose location")
        self.assertIn("TIER-2", blob.upper(), "PR-001 must name the tier-2 constitutional gate")
        self.assertIn("5A", blob, "PR-001 must name the section 5A loop as the resolution path")
        self.assertIn("OPEN-QUESTION", blob.upper(), "PR-001 must forward this as an OPEN-QUESTION")
        self.assertIn("T-348", blob, "PR-001 must name the epic join that escalates it")


class CitationResolutionTests(unittest.TestCase):
    """AC-5 'every citation resolves', read with SDR-12's requirement that
    PR-001 record the live P-023 gap via exactly one deliberately-dangling
    token. Verified two ways: via the CLI's own `cite --record` verb
    (replay, don't trust) and via the imported resolver directly."""

    def _dangling_via_module(self, rec):
        tokens = list(rec.get("cites", [])) + list(rec.get("tier_evidence", []))
        return [t for t in tokens if not precedent.resolve_citation(t, LIVE_REGISTRY)]

    def test_non_gap_records_have_zero_dangling_citations_cli(self):
        for pr_id in ("PR-002", "PR-003", "PR-004"):
            with self.subTest(pr_id=pr_id):
                result = run("cite", "--record", pr_id)
                self.assertEqual(result.returncode, 0,
                                  "{} cite --record: {}".format(pr_id, result.stdout + result.stderr))
                self.assertNotIn("DANGLING", result.stdout)

    def test_non_gap_records_have_zero_dangling_citations_module(self):
        for pr_id in ("PR-002", "PR-003", "PR-004"):
            with self.subTest(pr_id=pr_id):
                dangling = self._dangling_via_module(load_record(pr_id))
                self.assertEqual(dangling, [], "{}: {}".format(pr_id, dangling))

    def test_pr001_dangles_on_exactly_the_recorded_p023_gap_cli(self):
        result = run("cite", "--record", "PR-001")
        self.assertEqual(result.returncode, 3,
                          "PR-001 cite --record must report exactly the P-023 finding "
                          "(exit 3, SDR-15); got {}: {}".format(result.returncode, result.stdout))
        self.assertIn("cites P-023: DANGLING", result.stdout)
        self.assertEqual(result.stdout.count("DANGLING"), 1,
                          "PR-001 must dangle on exactly one token (P-023), not more: {}"
                          .format(result.stdout))

    def test_pr001_dangles_on_exactly_the_recorded_p023_gap_module(self):
        dangling = self._dangling_via_module(load_record("PR-001"))
        self.assertEqual(dangling, ["P-023"],
                          "PR-001 must dangle on exactly the recorded P-023 gap citation and "
                          "nothing else (SDR-12); got {}".format(dangling))


class ShowAndListCommandTests(unittest.TestCase):
    """AC-5: `precedent.py show PR-NNN` prints each of the four records."""

    def test_show_prints_each_seed_record(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                result = run("show", pr_id)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"id": "{}"'.format(pr_id), result.stdout)
                self.assertIn("scope: UNCONFIRMED (does not bind)", result.stdout)

    def test_list_shows_all_four_seed_records(self):
        result = run("list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        ids = sorted(entry["id"] for entry in payload)
        self.assertEqual(ids, list(SEED_IDS))
        for entry in payload:
            self.assertEqual(entry["confirmation_status"], "unconfirmed")


class NoMutationGuaranteeTests(unittest.TestCase):
    """T-343 AC-5: this suite is read-only against the live registry. Running
    show/list/cite must not change a single byte under .harness/precedents/
    (mirrors test_precedent_conflicts.py's own before/after snapshot
    convention for the identical property)."""

    def _snapshot(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(LIVE_REGISTRY.glob("PR-*.json"))}

    def test_reading_the_live_registry_does_not_mutate_it(self):
        before = self._snapshot()
        for pr_id in SEED_IDS:
            run("show", pr_id)
            run("cite", "--record", pr_id)
        run("list", "--json")
        after = self._snapshot()
        self.assertEqual(before, after, "reading the live registry must never mutate it")


if __name__ == "__main__":
    unittest.main()
