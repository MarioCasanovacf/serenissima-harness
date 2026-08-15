"""Tests for currency.py, the A.8 currency-health indicator (PR-023 clause 5).

The property that matters most here is a REFUSAL: this tool must never emit a pass/fail
verdict, because PR-023 clause 5 conditions Phase B on the indicator without defining a
failing point. A tool that invents that point has decided a tier-1 conjunction.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
LIVE = ROOT / ".harness"

sys.path.insert(0, str(BIN_DIR))
import currency  # noqa: E402


def rec(rid, by, cites=None, relations=None, confirmed_by=None):
    return {"id": rid, "published_by": by, "cites": cites or [],
            "relations": relations or [], "confirmed_by": confirmed_by,
            "published_at": "2026-08-15T00:00:00Z"}


def build(tmp, records):
    d = pathlib.Path(tmp) / "precedents"
    d.mkdir(parents=True, exist_ok=True)
    for r in records:
        (d / f"{r['id']}.json").write_text(json.dumps(r), encoding="utf-8")
    return pathlib.Path(tmp)


class ItRefusesToVerdict(unittest.TestCase):

    def test_no_output_path_emits_a_pass_or_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [rec("PR-001", "a"), rec("PR-002", "b", ["PR-001"])])
            out = currency.report(root)
        self.assertIn("NOT COMPUTED", out["VERDICT"])
        self.assertIn("NO THRESHOLD RATIFIED", out["VERDICT"])
        for section in ("A_8_1_convergence", "A_8_2_concentration"):
            self.assertIn("NO_THRESHOLD_RATIFIED", out[section])
        blob = json.dumps(out).lower()
        for banned in ('"pass"', '"fail"', '"failing": true', '"healthy"'):
            self.assertNotIn(banned, blob)

    def test_no_public_callable_takes_a_threshold(self):
        import inspect
        for name in currency.PUBLIC_API:
            fn = getattr(currency, name)
            if not callable(fn):
                continue
            for param in inspect.signature(fn).parameters:
                for bad in ("threshold", "limit", "cutoff", "verdict", "gate"):
                    self.assertNotIn(bad, param.lower(), f"{name}({param})")


class Convergence(unittest.TestCase):

    def test_a_bare_cite_is_a_name_drop_and_a_typed_relation_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [
                rec("PR-001", "a"),
                rec("PR-002", "b", cites=["PR-001"]),
                rec("PR-003", "c", relations=[{"target": "PR-001", "type": "follows"}]),
            ])
            c = currency.convergence(currency.load_records(root))
        self.assertEqual(c["bare_name_drop"], 1)
        self.assertEqual(c["typed_load_bearing_eligible"], 1)
        self.assertEqual(c["citation_edges_total"], 2)
        self.assertEqual(c["share_typed"], 0.5)

    def test_a_pair_that_is_both_bare_and_typed_counts_once_as_typed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [
                rec("PR-001", "a"),
                rec("PR-002", "b", cites=["PR-001"],
                    relations=[{"target": "PR-001", "type": "follows"}]),
            ])
            c = currency.convergence(currency.load_records(root))
        self.assertEqual(c["citation_edges_total"], 1)
        self.assertEqual(c["bare_name_drop"], 0)

    def test_distinguishes_is_not_counted_as_load_bearing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [
                rec("PR-001", "a"),
                rec("PR-002", "b",
                    relations=[{"target": "PR-001", "type": "distinguishes"}]),
            ])
            c = currency.convergence(currency.load_records(root))
        self.assertEqual(c["typed_load_bearing_eligible"], 0)

    def test_a_falling_typed_share_reads_as_DIVERGING(self):
        """Both halves must clear MIN_WINDOW_EDGES or no direction is named."""
        n = currency.MIN_WINDOW_EDGES
        early = [rec(f"PR-{i:03d}", "a",
                     relations=[{"target": f"PR-9{j:02d}", "type": "follows"}
                                for j in range(2)])
                 for i in range(1, n + 1)]
        late = [rec(f"PR-{i:03d}", "b", cites=[f"PR-9{j:02d}" for j in range(2)])
                for i in range(n + 1, 2 * n + 1)]
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, early + late)
            c = currency.convergence(currency.load_records(root))
        self.assertTrue(c["drift_is_reportable"])
        self.assertLess(c["drift_share_typed"], 0)
        self.assertIn("DIVERGING", c["DIRECTION"])

    def test_a_thin_window_refuses_to_name_a_direction(self):
        """The live registry's second half carries 6 edges. The first version of this
        tool called that `converging` and the figure reached the operator as a trend."""
        early = [rec(f"PR-{i:03d}", "a", cites=["PR-900"]) for i in range(1, 30)]
        late = [rec(f"PR-{i:03d}", "b",
                    relations=[{"target": "PR-900", "type": "follows"}])
                for i in range(30, 33)]
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, early + late)
            c = currency.convergence(currency.load_records(root))
        self.assertFalse(c["drift_is_reportable"])
        self.assertIn("NOT REPORTABLE", c["DIRECTION"])
        self.assertIsNotNone(c["drift_share_typed"], "the number still prints")


class Concentration(unittest.TestCase):

    def test_the_confirmation_signal_is_flagged_when_degenerate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [rec("PR-001", "a"), rec("PR-002", "b")])
            k = currency.concentration(currency.load_records(root))
        self.assertTrue(k["signal_1_is_degenerate"])
        self.assertIn("never once been exercised", k["signal_1_note"])

    def test_either_signal_counts_as_verified_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [
                rec("PR-001", "a"),                                   # built on by c
                rec("PR-002", "b", confirmed_by="d"),                 # confirmed
                rec("PR-003", "c", relations=[{"target": "PR-001", "type": "follows"}]),
                rec("PR-004", "e"),                                   # neither
            ])
            k = currency.concentration(currency.load_records(root))
        by = {r["identity"]: r for r in k["ranking"]}
        self.assertTrue(by["a"]["has_verified_work"])
        self.assertTrue(by["b"]["has_verified_work"])
        self.assertFalse(by["e"]["has_verified_work"])
        self.assertEqual(k["identities_without_verified_work"], ["c", "e"])

    def test_self_citation_does_not_confer_verified_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [
                rec("PR-001", "a"),
                rec("PR-002", "a", relations=[{"target": "PR-001", "type": "follows"}]),
            ])
            k = currency.concentration(currency.load_records(root))
        self.assertEqual(k["identities_without_verified_work"], ["a"])

    def test_self_confirmation_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [rec("PR-001", "a", confirmed_by="a")])
            k = currency.concentration(currency.load_records(root))
        self.assertEqual(k["identities_without_verified_work"], ["a"])

    def test_shares_carry_their_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(tmp, [rec(f"PR-{i:03d}", "a") for i in range(4)]
                         + [rec("PR-100", "b")])
            k = currency.concentration(currency.load_records(root))
        self.assertEqual(k["records_total"], 5)
        self.assertEqual(k["top1_share"], 0.8)


class ReadOnly(unittest.TestCase):

    def test_the_module_never_writes(self):
        """USE, not MENTION. The registry already carries GUARD-MENTION-C for exactly
        this: a scanner that reads prose as code. The docstring says the module does not
        call hc.log_event, and a naive substring scan reads that sentence as a call.
        So the check walks the AST and looks at what is actually invoked."""
        import ast
        tree = ast.parse((BIN_DIR / "currency.py").read_text(encoding="utf-8"))
        banned = {"write_text", "write_bytes", "atomic_write_json", "log_event",
                  "guarded", "mkdir", "append_jsonl", "unlink", "rename", "touch"}
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name:
                    called.add(name)
        self.assertEqual(called & banned, set(),
                         f"currency.py calls write verbs: {sorted(called & banned)}")
        self.assertNotIn("open", called, "currency.py opens a file handle")

    def test_running_it_against_the_live_registry_changes_nothing(self):
        import hashlib
        def digest():
            h = hashlib.sha256()
            for p in sorted((LIVE / "precedents").glob("*.json")):
                h.update(p.read_bytes())
            ev = LIVE / "logs" / "events.jsonl"
            h.update(ev.read_bytes() if ev.exists() else b"")
            return h.hexdigest()
        before = digest()
        subprocess.run([sys.executable, str(BIN_DIR / "currency.py"), "--json"],
                       capture_output=True, check=True)
        self.assertEqual(digest(), before)

    def test_an_empty_registry_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = currency.report(pathlib.Path(tmp))
        self.assertEqual(out["provenance"]["records_read"], 0)
        self.assertIsNone(out["A_8_1_convergence"]["share_typed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
