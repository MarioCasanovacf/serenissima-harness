"""Contention proof for the cross-platform lock backend (portalock).

The substrate's correctness rests on `portalock.lock_ex` serializing
read-modify-write cycles across processes. This test reproduces real
contention -- many OS processes hammering one shared file -- and asserts the
two properties the harness depends on:

  1. No lost updates: N processes each doing M guarded increments of a shared
     JSON counter must leave the counter at exactly N*M. A missing lock loses
     updates here immediately.
  2. No torn lines: concurrent guarded appends to one JSONL file must yield
     exactly the expected number of lines, each individually valid JSON.

It also confirms `harness_common` (which does `import portalock`) still loads
with `.harness/bin` on the path -- the wiring hooks rely on.

Platform-neutral by construction: it exercises whichever backend portalock
selects, so the same run proves the POSIX path on Unix/macOS and the msvcrt
path on Windows.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / ".harness" / "bin"
SELF = Path(__file__).resolve()


def _worker_rmw(lockfile, counterfile, iterations):
    sys.path.insert(0, str(BIN))
    import portalock

    for _ in range(int(iterations)):
        with open(lockfile, "a+") as fh:
            portalock.lock_ex(fh)
            try:
                try:
                    with open(counterfile, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    data = {"n": 0}
                data["n"] += 1
                fd, tmp = tempfile.mkstemp(dir=str(Path(counterfile).parent), suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(tmp, counterfile)
            finally:
                portalock.unlock(fh)


def _worker_append(jsonlfile, lines, tag):
    sys.path.insert(0, str(BIN))
    import portalock

    for i in range(int(lines)):
        with open(jsonlfile, "a", encoding="utf-8") as fh:
            portalock.lock_ex(fh)
            fh.write(json.dumps({"tag": tag, "i": i}) + "\n")
            portalock.unlock(fh)


# When re-invoked as a child process, act as the worker rather than a test.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--worker":
    if sys.argv[2] == "rmw":
        _worker_rmw(sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        _worker_append(sys.argv[3], sys.argv[4], sys.argv[5])
    sys.exit(0)


class PortalockContentionTest(unittest.TestCase):
    PROCS = 8

    def _spawn(self, args):
        return subprocess.Popen([sys.executable, str(SELF), "--worker", *args])

    def test_guarded_rmw_has_no_lost_updates(self):
        iters = 60
        with tempfile.TemporaryDirectory() as d:
            lockfile = str(Path(d) / ".guard")
            counterfile = str(Path(d) / "counter.json")
            children = [
                self._spawn(["rmw", lockfile, counterfile, str(iters)])
                for _ in range(self.PROCS)
            ]
            for c in children:
                self.assertEqual(c.wait(timeout=120), 0)
            with open(counterfile, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f)["n"], self.PROCS * iters)

    def test_concurrent_appends_have_no_torn_lines(self):
        lines = 80
        with tempfile.TemporaryDirectory() as d:
            jsonlfile = str(Path(d) / "events.jsonl")
            children = [
                self._spawn(["append", jsonlfile, str(lines), "w{}".format(i)])
                for i in range(self.PROCS)
            ]
            for c in children:
                self.assertEqual(c.wait(timeout=120), 0)
            with open(jsonlfile, "r", encoding="utf-8") as f:
                rows = f.readlines()
            self.assertEqual(len(rows), self.PROCS * lines)
            for row in rows:  # every line must be independently parseable
                json.loads(row)

    def test_harness_common_imports_with_portalock(self):
        spec = importlib.util.spec_from_file_location(
            "harness_common", BIN / "harness_common.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(BIN))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        self.assertTrue(hasattr(module, "guarded"))


if __name__ == "__main__":
    unittest.main()
