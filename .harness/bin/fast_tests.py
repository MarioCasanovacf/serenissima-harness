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
    python3 .harness/bin/fast_tests.py --changed      # only the tests the working-tree diff touches
    python3 .harness/bin/fast_tests.py --changed --base HEAD~3   # diff against another commit

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

--changed RUNS ONLY WHAT YOUR CHANGE TOUCHES. Measured on 2026-11-17: four agents each
running the full suite at once saturated ten cores; each run took 2 to 4 min instead of
55 s, and the machine became unusable. With --changed the runner reads the working-tree
diff against HEAD (`git diff --name-only HEAD`, plus untracked files; --base REF diffs
against another commit) and selects, by a static scan and nothing smarter:
  - every changed test file (tests/test_*.py), picked as itself;
  - every test file that imports a changed module under .harness/bin or examples/ (an
    import line whose module path holds that module's name), or names its file name
    (for example 'attest.py') anywhere in the test source.
The selection prints, with the reason for each file. A change that no test references
selects NOTHING: the runner says so and exits 5 (pytest's no-tests code). It never
falls back to the full suite on its own; run it without --changed for that. The scan is
static: a module reached only through another module, or loaded by a string built at run
time, is not seen, so --changed is a quick check, not the last gate before a merge.
--changed cannot be combined with named test files; -k still narrows the selection.

LOW PRIORITY AND HALF THE CORES. Children run at nice 10 (os.nice; --nice N sets it,
0 to 19), so a run never starves the person at the keyboard. The machine-wide slot cap
defaults to half the cores (10 cores: 5 slots) and the environment variable
HARNESS_TEST_SLOTS overrides it. -j cannot exceed the cap; asking for more prints a
note and uses the cap. The cap is per slot FILE, so runs that disagree about it still
share the files below the smaller number.
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

DEFAULT_NICE = 10
SLOTS_ENV = "HARNESS_TEST_SLOTS"
# Source trees whose .py files count as "a changed module" for --changed.
MODULE_DIRS = (".harness/bin/", "examples/")
SPLIT_AT_S = 6.0
BATCHES_PER_JOB = 2
BATCH_TIMEOUT_S = 900
SUMMARY_RE = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected)")
DURATION_RE = re.compile(r"^\s*([\d.]+)s (setup|call|teardown)\s+(\S+)\s*$")


def slot_cap():
    """The machine-wide cap on pytest children: half the cores, or $HARNESS_TEST_SLOTS."""
    raw = os.environ.get(SLOTS_ENV, "").strip()
    if raw:
        try:
            if int(raw) >= 1:
                return int(raw)
        except ValueError:
            pass
        print("fast_tests: ignoring %s=%r (want a whole number of 1 or more)"
              % (SLOTS_ENV, raw), file=sys.stderr)
    return max(1, (os.cpu_count() or 2) // 2)


def default_jobs():
    return max(1, min(8, (os.cpu_count() or 2) - 2, slot_cap()))


def effective_jobs(requested):
    """-j, never above the slot cap (the cap is what keeps parallel runs from piling up)."""
    return max(1, min(requested, slot_cap()))


def apply_nice(level):
    """Raise this process to niceness `level` (0 to 19). Every child inherits it. Idempotent
    for a runner already niced, and silent where os.nice does not exist or is refused."""
    level = max(0, min(19, level))
    try:
        delta = level - os.nice(0)
        if delta > 0:
            os.nice(delta)
        return os.nice(0)
    except (AttributeError, OSError):
        return None


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
    """A machine-wide cap of slot_cap() pytest children (half the cores unless
    HARNESS_TEST_SLOTS says otherwise), so several runs at once (agents in parallel)
    share the cores instead of oversubscribing them. Each worker thread owns one slot
    index; a slot is a file held under portalock's exclusive lock (the one module
    allowed to touch fcntl), so worker k of every concurrent run queues on the same
    file, and at most slot_cap() children run machine-wide."""

    def __enter__(self):
        if not hasattr(_slot_ids, "i"):
            with _slot_guard:
                _slot_ids.i = _slot_next[0] % slot_cap()
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


def git_changed(repo, base="HEAD"):
    """Paths (repo-relative, posix) changed in the working tree against `base`, plus
    untracked files that are not ignored. Raises RuntimeError if git cannot say."""
    def run(*args):
        p = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True,
                           text=True, timeout=60)
        if p.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(args), p.stderr.strip()))
        return [x for x in p.stdout.split("\0") if x]
    return sorted(set(run("diff", "--name-only", "-z", base, "--")) |
                  set(run("ls-files", "--others", "--exclude-standard", "-z")))


def imported_names(source):
    """Every dotted-name word on the import lines of one Python source: for
    'from a.b import c, d' and 'import e.f as g' the words a, b, c, d, e, f, g."""
    words = set()
    for line in source.splitlines():
        m = re.match(r"\s*(?:from|import)\s+(.*)", line)
        if m:
            words.update(re.findall(r"[A-Za-z_]\w*", m.group(1)))
    return words


def select_changed(repo, changed):
    """(picked, ignored): picked maps a test file Path to the reasons it was chosen;
    ignored lists the changed paths that led to no test. Static scan only."""
    repo = pathlib.Path(repo)
    tests = sorted((repo / ".harness" / "tests").glob("test_*.py"))
    sources = {}
    for t in tests:
        try:
            sources[t] = t.read_text(encoding="utf-8", errors="replace")
        except OSError:
            sources[t] = ""
    imports = {t: imported_names(src) for t, src in sources.items()}
    picked, ignored = {}, []
    for rel in changed:
        hit = False
        path = repo / rel
        if rel.startswith(".harness/tests/") and path.name.startswith("test_") \
                and path.suffix == ".py" and path in sources:
            picked.setdefault(path, []).append("changed itself")
            hit = True
        if rel.endswith(".py") and any(rel.startswith(d) for d in MODULE_DIRS):
            stem, fname = pathlib.PurePosixPath(rel).stem, pathlib.PurePosixPath(rel).name
            name_re = re.compile(r"(?<![\w.])%s(?!\w)" % re.escape(fname))
            for t in tests:
                if stem in imports[t]:
                    picked.setdefault(t, []).append("imports changed module %s" % rel)
                    hit = True
                elif name_re.search(sources[t]):
                    picked.setdefault(t, []).append("names changed file %s" % fname)
                    hit = True
        if not hit:
            ignored.append(rel)
    return picked, ignored


def label(batch):
    ids = batch["ids"]
    return ids[0] if len(ids) == 1 else "%s and %d more" % (ids[0], len(ids) - 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", help="test files to run (default: all)")
    ap.add_argument("-j", "--jobs", type=int, default=default_jobs(),
                    help="workers; never above the slot cap (half the cores, or "
                         "$%s)" % SLOTS_ENV)
    ap.add_argument("--changed", action="store_true",
                    help="only the test files the working-tree diff touches")
    ap.add_argument("--base", default="HEAD", metavar="REF",
                    help="with --changed: diff against REF instead of HEAD")
    ap.add_argument("--nice", type=int, default=DEFAULT_NICE, metavar="N",
                    help="niceness of the runner and its children, 0 to 19 "
                         "(default %d)" % DEFAULT_NICE)
    ap.add_argument("-k", "--keyword", help="only files whose name contains this text")
    ap.add_argument("--serial", action="store_true", help="plain pytest, one process")
    ap.add_argument("--plan", action="store_true", help="print the batches and exit")
    ap.add_argument("--pytest-arg", action="append", default=[],
                    help="extra argument for every pytest process (repeatable)")
    a = ap.parse_args(argv)

    if a.changed and (a.files or a.serial):
        ap.error("--changed cannot be combined with named test files or --serial")
    if a.base != "HEAD" and not a.changed:
        ap.error("--base only makes sense with --changed")
    apply_nice(a.nice)

    if a.serial:
        return subprocess.call([sys.executable, "-m", "pytest", str(TESTS), "-q",
                                "-p", "no:cacheprovider"] + a.pytest_arg, cwd=str(REPO))

    cap = slot_cap()
    if a.jobs > cap:
        print("fast_tests: -j %d is above the slot cap of %d (half the cores, or $%s); "
              "using %d" % (a.jobs, cap, SLOTS_ENV, cap))
    a.jobs = effective_jobs(a.jobs)

    if a.changed:
        try:
            changed = git_changed(REPO, a.base)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            print("fast_tests: --changed cannot read the diff: %s" % e)
            return 2
        picked, ignored = select_changed(REPO, changed)
        if a.keyword:
            picked = {t: r for t, r in picked.items() if a.keyword in t.name}
        print("fast_tests: --changed against %s: %d changed paths, %d test files selected"
              % (a.base, len(changed), len(picked)))
        for t in sorted(picked):
            print("  %s  (%s)" % (t.name, "; ".join(dict.fromkeys(picked[t]))))
        for rel in ignored:
            print("  no test references %s" % rel)
        if not picked:
            print("fast_tests: nothing selected, so nothing ran. No test is changed or "
                  "references a changed module; run without --changed for the full suite.")
            return 5
        files = sorted(picked)
    else:
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
    ok = all(r["ok"] for r in results)
    log_tests_run(files, total, wall, ok, a.changed)
    return 0 if ok else 1


def log_tests_run(files, total, wall, ok, changed):
    """One `tests_run` event (files, counts, seconds) for the console's activity
    tooltip. Observability only: any failure here is ignored."""
    try:
        import harness_common as hc
        hc.log_event("tests_run", files=[f.name for f in files][:50], file_count=len(files),
                     counts=total, seconds=round(wall, 1), ok=ok, changed=bool(changed))
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
