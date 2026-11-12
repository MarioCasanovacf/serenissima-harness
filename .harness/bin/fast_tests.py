#!/usr/bin/env python3
"""fast_tests.py - the full test suite on every core, same verdict as serial pytest.

Measured on 2026-11-12: serial pytest over .harness/tests took 166 s on one core of
ten, and full-suite runs were a third of all agent time in a gen-10 wave. Standard
library only.

    python3 .harness/bin/fast_tests.py                # whole suite, parallel
    python3 .harness/bin/fast_tests.py -j 4           # four workers
    python3 .harness/bin/fast_tests.py -k attest      # files whose name contains 'attest'
    python3 .harness/bin/fast_tests.py test_a.py ...  # only these files (partial run)
    python3 .harness/bin/fast_tests.py --serial       # plain pytest, one process

The last line has pytest's own shape ('N passed, M skipped in S s'). Exit 0 only when
every batch passes.

HOW THE WORK IS CUT. Tests are grouped into a few BATCHES, about two per worker, each
one pytest process, balanced by each test's time on the previous run (pytest's own
--durations report, kept in an untracked store). A slow file is cut by class and a slow
class by test, so no single file sets the floor. Few processes on purpose: each
process start is expensive on a machine whose security agent inspects every spawn.

SERIAL FILES RUN LAST. Files in SERIAL compare the live tree before and after, so a
neighbour's write can fail them. They run after everything else has finished, beside
each other only; if one still fails, it runs once more alone, and the alone run is the
verdict. A real failure reproduces alone; a collision does not. Every retry is printed.

Children run with PYTHONDONTWRITEBYTECODE=1, so the runner never writes cache files
into the live tree that SERIAL files hash. A machine-wide slot cap (fcntl) lets several
runs at once, from agents in parallel, share the cores instead of oversubscribing them.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import portalock  # noqa: E402  (the harness's one fcntl wrapper)
HARNESS = HERE.parent
REPO = HARNESS.parent
TESTS = HARNESS / "tests"
# Untracked (.gitignore): per-machine test times and collected ids; only orders work.
STORE = HARNESS / "logs" / "test_durations.json"
SLOT_DIR = pathlib.Path(tempfile.gettempdir()) / "harness-fast-tests-slots"

# file name -> why it cannot be trusted beside other test files
SERIAL = {
    "test_rehearsal.py": "hashes the live .harness tree and git status before and after "
                         "the rehearsal; a concurrent write elsewhere fails it",
}

SPLIT_AT_S = 6.0
BATCHES_PER_JOB = 2
BATCH_TIMEOUT_S = 900
SUMMARY_RE = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected)")
DURATION_RE = re.compile(r"^\s*([\d.]+)s (setup|call|teardown)\s+(\S+)\s*$")


def default_jobs():
    return max(1, min(8, (os.cpu_count() or 2) - 2))


def child_env():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def load_store():
    try:
        d = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("version") == 2:
            return d
    except Exception:
        pass
    return {"version": 2, "tests": {}, "ids": {}}


def save_store(store):
    try:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(store, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        pass  # times only order the work; never fail a run over them


def file_sig(path):
    st = path.stat()
    return "%d:%d" % (st.st_size, st.st_mtime_ns)


def parse_counts(text):
    """Counts from pytest's final summary line, e.g. '3 failed, 40 passed in 1.2s'."""
    for line in reversed(text.strip().splitlines()):
        if " in " not in line:
            continue
        found = SUMMARY_RE.findall(line)
        if found:
            counts = {}
            for n, kind in found:
                kind = "errors" if kind.startswith("error") else kind
                counts[kind] = counts.get(kind, 0) + int(n)
            return counts
    return {}


def parse_durations(text):
    """nodeid -> seconds (setup + call + teardown) from pytest's --durations report."""
    out = {}
    for line in text.splitlines():
        m = DURATION_RE.match(line)
        if m:
            out[m.group(3)] = out.get(m.group(3), 0.0) + float(m.group(1))
    return out


def failing_ids(out):
    return [m.group(2) for m in (re.match(r"^(FAILED|ERROR) (\S+)", l)
                                 for l in out.splitlines()) if m]


def collect_ids(rel):
    """Every test node id in one file, from pytest's own collection."""
    p = subprocess.run([sys.executable, "-m", "pytest", rel, "--collect-only", "-q",
                        "-p", "no:cacheprovider"], cwd=str(REPO), capture_output=True,
                       text=True, env=child_env(), timeout=300)
    if p.returncode != 0:
        return []
    return [l.strip() for l in p.stdout.splitlines() if l.startswith(rel + "::")]


def plan_units(files, store):
    """(node id, file name, estimated seconds). A slow file is cut by class, a slow
    class by test; times are the previous run's, file size stands in for a new file."""
    times = store["tests"]

    def est(key):
        vals = [v for k, v in times.items() if k == key or k.startswith(key + "::")]
        return sum(vals) if vals else None

    units = []
    for f in files:
        rel = f.relative_to(REPO).as_posix()
        t = est(rel)
        if t is None or t < SPLIT_AT_S:
            units.append((rel, f.name, t if t is not None else f.stat().st_size / 2000.0))
            continue
        cached = store["ids"].get(rel)
        if cached and cached.get("sig") == file_sig(f):
            ids = cached["ids"]
        else:
            ids = collect_ids(rel)
            store["ids"][rel] = {"sig": file_sig(f), "ids": ids}
        if not ids:
            units.append((rel, f.name, t))
            continue
        classes = []
        for i in ids:
            parts = i.split("::")
            c = "::".join(parts[:2]) if len(parts) > 2 else i
            if c not in classes:
                classes.append(c)
        for c in classes:
            members = [i for i in ids if i.startswith(c + "::")]
            ct = est(c) or 0.0
            if ct >= SPLIT_AT_S and len(members) > 1:
                units.extend((m, f.name, est(m) or ct / len(members)) for m in members)
            else:
                units.append((c, f.name, ct))
    return units


def pack(units, jobs):
    """SERIAL units: one batch each. The rest: longest-first into the least-loaded of
    about two batches per worker. Returns batches, serial first, then heaviest first."""
    serial = [{"ids": [u[0]], "load": u[2], "serial": True} for u in units if u[1] in SERIAL]
    rest = sorted((u for u in units if u[1] not in SERIAL), key=lambda u: -u[2])
    n = max(1, min(len(rest), jobs * BATCHES_PER_JOB))
    bins = [{"ids": [], "load": 0.0, "serial": False} for _ in range(n)]
    for u in rest:
        b = min(bins, key=lambda b: b["load"])
        b["ids"].append(u[0])
        b["load"] += u[2]
    bins = [b for b in bins if b["ids"]]
    return serial + sorted(bins, key=lambda b: -b["load"])


_slot_ids = threading.local()
_slot_next = [0]
_slot_guard = threading.Lock()


class Slot:
    """A machine-wide cap of default_jobs() pytest children, so several runs at once
    (agents in parallel) share the cores instead of oversubscribing them. Each worker
    thread owns one slot index; a slot is a file held under portalock's exclusive lock
    (the one module allowed to touch fcntl), so worker k of every concurrent run queues
    on the same file, and at most default_jobs() children run machine-wide."""

    def __enter__(self):
        if not hasattr(_slot_ids, "i"):
            with _slot_guard:
                _slot_ids.i = _slot_next[0] % default_jobs()
                _slot_next[0] += 1
        SLOT_DIR.mkdir(parents=True, exist_ok=True)
        self.fh = open(SLOT_DIR / ("slot-%d" % _slot_ids.i), "a+")
        portalock.lock_ex(self.fh)
        return self

    def __exit__(self, *exc):
        try:
            portalock.unlock(self.fh)
        finally:
            self.fh.close()
        return False


def run_batch(batch, extra):
    cmd = ([sys.executable, "-m", "pytest"] + batch["ids"] +
           ["-q", "-p", "no:cacheprovider", "--durations=0", "--durations-min=0"] + extra)
    with Slot():
        t0 = time.monotonic()
        try:
            p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                               timeout=BATCH_TIMEOUT_S, env=child_env())
            out, code = p.stdout + p.stderr, p.returncode
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else ""
            out += "\nTIMEOUT: batch ran longer than %d s and was stopped" % BATCH_TIMEOUT_S
            code = -1
        took = time.monotonic() - t0
    counts = parse_counts(out)
    ok = code == 0 or (code == 5 and not counts.get("failed") and not counts.get("errors"))
    if not ok and not counts.get("failed") and not counts.get("errors"):
        counts["errors"] = 1  # crashed, timed out or failed to import: counted, never hidden
    return {"batch": batch, "ok": ok, "code": code, "took": took, "counts": counts,
            "out": out, "times": parse_durations(out)}


def select(names, keyword):
    files = sorted(TESTS.glob("test_*.py"))
    if names:
        wanted = {pathlib.Path(n).name for n in names}
        missing = wanted - {f.name for f in files}
        if missing:
            sys.exit("fast_tests: no such test file: %s" % ", ".join(sorted(missing)))
        files = [f for f in files if f.name in wanted]
    if keyword:
        files = [f for f in files if keyword in f.name]
    return files


def label(batch):
    ids = batch["ids"]
    return ids[0] if len(ids) == 1 else "%s and %d more" % (ids[0], len(ids) - 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", help="test files to run (default: all)")
    ap.add_argument("-j", "--jobs", type=int, default=default_jobs())
    ap.add_argument("-k", "--keyword", help="only files whose name contains this text")
    ap.add_argument("--serial", action="store_true", help="plain pytest, one process")
    ap.add_argument("--plan", action="store_true", help="print the batches and exit")
    ap.add_argument("--pytest-arg", action="append", default=[],
                    help="extra argument for every pytest process (repeatable)")
    a = ap.parse_args(argv)

    if a.serial:
        return subprocess.call([sys.executable, "-m", "pytest", str(TESTS), "-q",
                                "-p", "no:cacheprovider"] + a.pytest_arg, cwd=str(REPO))

    files = select(a.files, a.keyword)
    if not files:
        print("fast_tests: no test files selected")
        return 5
    store = load_store()
    batches = pack(plan_units(files, store), max(1, a.jobs))
    if a.plan:
        for b in batches:
            print("%6.1fs %s%s" % (b["load"], "SERIAL " if b["serial"] else "", label(b)))
        save_store(store)
        return 0

    t0 = time.monotonic()
    results = []
    # Phase 1: everything that may share the machine. Phase 2: SERIAL batches, beside
    # each other only (each hashes the live tree; none writes it), after phase 1 drains.
    phase_walls = []
    for phase in ([b for b in batches if not b["serial"]], [b for b in batches if b["serial"]]):
        tp = time.monotonic()
        with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
            futs = [pool.submit(run_batch, b, a.pytest_arg) for b in phase]
            for fut in as_completed(futs):
                results.append(fut.result())
        phase_walls.append(time.monotonic() - tp)
    retried = []
    for i, r in enumerate(results):
        if not r["ok"] and r["batch"]["serial"]:
            alone = run_batch(r["batch"], a.pytest_arg)
            retried.append((label(r["batch"]), alone["ok"]))
            results[i] = alone
    wall = time.monotonic() - t0

    live = {f.relative_to(REPO).as_posix() for f in TESTS.glob("test_*.py")}
    store["tests"] = {k: v for k, v in store["tests"].items() if k.split("::")[0] in live}
    for r in results:
        store["tests"].update({k: round(v, 3) for k, v in r["times"].items()})
    save_store(store)

    total = {}
    for r in results:
        for k, v in r["counts"].items():
            total[k] = total.get(k, 0) + v
    for name, ok in retried:
        print("RETRIED ALONE: %s failed beside other batches; alone it %s"
              % (name, "passed" if ok else "FAILED again, so the failure is real"))
    for r in sorted((r for r in results if not r["ok"]), key=lambda r: label(r["batch"])):
        print("=" * 70)
        print("FAILED BATCH %s (exit %s)" % (label(r["batch"]), r["code"]))
        for i in failing_ids(r["out"]):
            print("  " + i)
        body = [l for l in r["out"].strip().splitlines() if not DURATION_RE.match(l)]
        print("\n".join(body[-40:]))
    order = ["failed", "errors", "passed", "skipped", "xfailed", "xpassed", "deselected"]
    parts = ["%d %s" % (total[k], k) for k in order if total.get(k)]
    print("%s in %.2fs (%d files in %d batches, %d workers; shared phase %.0fs, serial "
          "phase %.0fs, %d retried alone)"
          % (", ".join(parts) or "no tests ran", wall, len(files), len(results), a.jobs,
             phase_walls[0], phase_walls[1], len(retried)))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
