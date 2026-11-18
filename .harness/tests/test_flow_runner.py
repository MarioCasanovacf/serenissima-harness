"""Tests for flow_runner.py (design T-484 sections 3, 4 and 8).

Every test runs in a throwaway root with copied harness tools and an empty board.
HARNESS_CLAUDE_BIN points at a fake CLI that acts on the throwaway board through
blackboard.py, the way a real agent would, and prints a scripted final result. No test
calls a model or touches the live board.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
sys.path.insert(0, str(BIN_DIR))
import flow_runner as fr  # noqa: E402
import operator_desk as od  # noqa: E402

FAKE_CLI = textwrap.dedent('''\
    import json, os, subprocess, sys
    prompt = sys.stdin.read()
    agent = os.environ["CLAUDE_HARNESS_AGENT_ID"]
    calls = os.environ["FAKE_CALLS"]
    with open(calls, "a") as f:
        f.write(json.dumps({"agent": agent, "argv": sys.argv[1:], "prompt": prompt}) + "\\n")
    with open(calls) as f:
        n = sum(1 for line in f if json.loads(line)["agent"] == agent)
    plan = json.load(open(os.environ["FAKE_PLAN"])).get(agent, [])
    act, task = plan[min(n, len(plan)) - 1] if plan else ("nothing", "")
    bb = [sys.executable, ".harness/bin/blackboard.py"]
    def run(*a):
        subprocess.run(bb + list(a) + ["--agent", agent], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if act == "produce":
        run("claim", task)
        run("handoff", task, "--to-role", "verifier", "--note", "built it")
    elif act == "approve":
        run("update", task, "--status", "done", "--note", "checked")
    elif act == "reject":
        run("update", task, "--status", "open", "--note", "REJECTED: not yet")
    elif act == "crash":
        sys.stderr.write("the fake fell over\\n")
        sys.exit(1)
    # "lie_<act>" does nothing on the board but reports exactly what "<act>" reports.
    shown = act[4:] if act.startswith("lie_") else act
    print("working...")
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "duration_ms": 12, "num_turns": 3, "result": "did " + shown}))
''')

FAKE_SUITE = 'print("collecting")\nprint("7 passed, 1 skipped in 0.42s")\n'


def recipe(**over):
    r = {
        "name": "demo",
        "description": "a demo flow",
        "tests": "changed",
        "gate": True,
        "defaults": {"model": "sonnet", "effort": "high", "rounds": 2},
        "tracks": [{"task": "T-901", "verify_task": "T-902", "producer": "worker-a",
                    "verifier": "verifier-a", "title": "build the thing",
                    "brief": "Build the thing and test it."}],
    }
    r.update(over)
    return r


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.root = self.base / "repo"
        h = self.root / ".harness"
        h.mkdir(parents=True)
        shutil.copytree(str(BIN_DIR), str(h / "bin"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (h / "bin" / "fast_tests.py").write_text(FAKE_SUITE)
        for d in ("tasks", "locks", "logs", "flows"):
            (h / d).mkdir()
        (h / "blackboard.json").write_text(json.dumps(
            {"schema_version": "0.1.0", "generation": 1, "tasks": {}, "announcements": []}))
        (h / "state.json").write_text(json.dumps({"limits": {}}))
        self.cli = self.base / "fake_claude.py"
        self.cli.write_text(FAKE_CLI)
        self.cli.chmod(0o755)
        wrapper = self.base / "fake_claude"
        wrapper.write_text("#!/bin/sh\nexec {} {} \"$@\"\n".format(sys.executable, self.cli))
        wrapper.chmod(0o755)
        self.calls = self.base / "calls.jsonl"
        self.plan = self.base / "plan.json"
        env = {"HARNESS_CLAUDE_BIN": str(wrapper), "FAKE_CALLS": str(self.calls),
               "FAKE_PLAN": str(self.plan)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("CLAUDE_HARNESS_AGENT_ID", None)

    def set_plan(self, plan):
        self.plan.write_text(json.dumps(plan))

    def write_recipe(self, r):
        (self.root / ".harness" / "flows" / (r["name"] + ".json")).write_text(json.dumps(r))

    def board(self):
        return json.loads((self.root / ".harness" / "blackboard.json").read_text())["tasks"]

    def call_log(self):
        if not self.calls.exists():
            return []
        return [json.loads(l) for l in self.calls.read_text().splitlines()]

    def events(self):
        p = self.root / ".harness" / "logs" / "events.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class TestValidate(Fixture):
    def problems(self, r):
        return fr.validate(self.root, r, r.get("name"))

    def test_the_shipped_example_validates_in_a_throwaway_root(self):
        r = json.loads((ROOT / ".harness" / "flows" / "example-wave.json").read_text())
        self.assertEqual(self.problems(r), [])

    def test_a_good_recipe_has_no_problems(self):
        self.assertEqual(self.problems(recipe()), [])

    def assertRefused(self, r, fragment):
        probs = self.problems(r)
        self.assertTrue(any(fragment in p for p in probs), probs)

    def test_unknown_keys_are_refused(self):
        self.assertRefused(recipe(colour="red"), "unknown keys: colour")
        r = recipe()
        r["tracks"][0]["shell"] = "rm"
        self.assertRefused(r, "unknown keys: shell")

    def test_a_task_not_on_the_board_needs_a_title(self):
        r = recipe()
        del r["tracks"][0]["title"]
        self.assertRefused(r, "T-901 is not on the board")

    def test_the_producer_cannot_be_its_own_verifier(self):
        r = recipe()
        r["tracks"][0]["verifier"] = "worker-a"
        self.assertRefused(r, "cannot be its own verifier")

    def test_rounds_outside_one_to_three(self):
        for bad in (0, 4, "2", True):
            r = recipe()
            r["tracks"][0]["rounds"] = bad
            self.assertRefused(r, "rounds must be 1, 2 or 3")

    def test_skip_permission_flags_are_denied(self):
        for flags in (["--dangerously-skip-permissions"],
                      ["--allow-dangerously-skip-permissions"],
                      ["--permission-mode", "bypassPermissions"],
                      ["--permission-mode", "acceptEdits", "--dangerously-skip-permissions"]):
            r = recipe(defaults={"permissions": flags})
            probs = self.problems(r)
            self.assertTrue(probs, flags)

    def test_unknown_permission_flags_are_refused(self):
        self.assertRefused(recipe(defaults={"permissions": ["--add-dir", "/"]}),
                           "not an allowed permission flag")

    def test_reserved_and_shared_names(self):
        r = recipe()
        r["tracks"][0]["producer"] = "operator"
        self.assertRefused(r, "reserved name")
        r = recipe()
        r["tracks"].append({"task": "T-903", "verify_task": "T-904", "producer": "worker-a",
                            "verifier": "verifier-b", "title": "t", "brief": "b"})
        self.assertRefused(r, "already works another track")

    def test_a_leak_in_the_brief_is_refused(self):
        r = recipe()
        r["tracks"][0]["brief"] = "see /Us" + "ers/jdoe/notes.txt"
        self.assertRefused(r, "leak")

    def test_name_must_match_the_file(self):
        self.assertTrue(any("does not match the file name" in p for p in
                            fr.validate(self.root, recipe(name="other"), "demo")))
        self.assertEqual(fr.validate(self.root, recipe(name="other"), "other"), [])

    def test_save_refuses_an_invalid_recipe_and_writes_a_valid_one(self):
        with self.assertRaises(fr.Refused):
            fr.save_recipe(self.root, "demo", recipe(tests="all"))
        self.assertFalse((self.root / ".harness" / "flows" / "demo.json").exists())
        fr.save_recipe(self.root, "demo", recipe())
        self.assertEqual(fr.load_recipe(self.root, "demo")["name"], "demo")

    def test_flow_names_cannot_climb_out(self):
        with self.assertRaises(fr.Refused):
            fr.recipe_path(self.root, "../evil")


class TestEnqueue(Fixture):
    def test_enqueue_creates_the_tasks_and_starts_nothing(self):
        self.write_recipe(recipe())
        run = fr.launch(self.root, "demo", "enqueue")
        self.assertEqual(run["status"], "enqueued")
        self.assertEqual(sorted(run["created_tasks"]), ["T-901", "T-902"])
        tasks = self.board()
        self.assertEqual(tasks["T-902"]["depends_on"], ["T-901"])
        self.assertEqual(tasks["T-901"]["epic"], "flow:demo")
        self.assertEqual(self.call_log(), [])
        again = fr.launch(self.root, "demo", "enqueue")
        self.assertEqual(again["created_tasks"], [])
        self.assertNotEqual(again["id"], run["id"])
        self.assertEqual(len(fr.list_runs(self.root)), 2)

    def test_an_invalid_recipe_launches_nothing(self):
        r = recipe()
        r["tracks"][0]["verifier"] = "worker-a"
        self.write_recipe(r)
        with self.assertRaises(fr.Refused):
            fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual(self.board(), {})
        self.assertFalse((self.root / ".harness" / "runs").exists())


class TestAgents(Fixture):
    def test_produce_verify_done_then_the_gate_waits(self):
        self.write_recipe(recipe())
        self.set_plan({"worker-a": [["produce", "T-901"]],
                       "verifier-a": [["approve", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual(run["status"], "awaiting_operator")
        self.assertEqual([(s["role"], s["verdict"]) for s in run["steps"]],
                         [("producer", "review"), ("verifier", "done")])
        self.assertEqual(run["tracks"][0]["status"], "done")
        self.assertEqual(run["gate"]["status"], "pending")
        self.assertEqual(run["gate"]["suite"]["counts"], {"passed": 7, "skipped": 1})
        self.assertEqual(self.board()["T-901"]["status"], "done")
        calls = self.call_log()
        self.assertEqual([c["agent"] for c in calls], ["worker-a", "verifier-a"])
        for c in calls:
            self.assertIn("-p", c["argv"])
            self.assertEqual(c["argv"][c["argv"].index("--output-format") + 1], "json")
            self.assertNotIn("--dangerously-skip-permissions", c["argv"])
            self.assertNotIn("bypassPermissions", c["argv"])
            self.assertIn("never the full suite", c["prompt"])
        self.assertIn("T-901", calls[0]["prompt"])
        self.assertIn("Build the thing", calls[0]["prompt"])
        result = json.loads((self.root / ".harness" / "runs" / run["id"] /
                             run["steps"][0]["result_file"]).read_text())
        self.assertEqual(result["result"], "did produce")
        self.assertNotIn("working...", json.dumps(result))

    def test_a_sent_back_task_gets_a_second_round(self):
        self.write_recipe(recipe())
        self.set_plan({"worker-a": [["produce", "T-901"], ["produce", "T-901"]],
                       "verifier-a": [["reject", "T-901"], ["approve", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual([(s["role"], s["round"], s["verdict"]) for s in run["steps"]],
                         [("producer", 1, "review"), ("verifier", 1, "open"),
                          ("producer", 2, "review"), ("verifier", 2, "done")])
        self.assertEqual(run["tracks"][0]["status"], "done")

    def test_rounds_run_out(self):
        r = recipe()
        r["tracks"][0]["rounds"] = 1
        self.write_recipe(r)
        self.set_plan({"worker-a": [["produce", "T-901"]],
                       "verifier-a": [["reject", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual(len(run["steps"]), 2)
        self.assertEqual(run["tracks"][0]["status"], "sent back")

    def test_the_verdict_comes_from_the_board_not_the_text(self):
        self.write_recipe(recipe(gate=False))
        self.set_plan({"worker-a": [["nothing", ""]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual(len(run["steps"]), 1)
        self.assertTrue(run["tracks"][0]["status"].startswith("failed"))
        self.assertEqual(run["status"], "failed")

    def test_a_verifier_that_reports_approval_without_acting_is_not_done(self):
        r = recipe(gate=False)
        r["tracks"][0]["rounds"] = 1
        self.write_recipe(r)
        self.set_plan({"worker-a": [["produce", "T-901"]],
                       "verifier-a": [["lie_approve", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        said = json.loads((self.root / ".harness" / "runs" / run["id"] /
                           run["steps"][1]["result_file"]).read_text())["result"]
        self.assertEqual(said, "did approve")  # the text claims what an approval claims
        self.assertEqual([(s["role"], s["verdict"]) for s in run["steps"]],
                         [("producer", "review"), ("verifier", "review")])
        self.assertTrue(run["tracks"][0]["status"].startswith("failed"), run["tracks"])
        self.assertEqual(run["status"], "failed")
        self.assertEqual(self.board()["T-901"]["status"], "review")

    def test_a_producer_that_reports_work_without_acting_fails(self):
        self.write_recipe(recipe(gate=False))
        self.set_plan({"worker-a": [["lie_produce", "T-901"]],
                       "verifier-a": [["approve", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual([(s["role"], s["verdict"]) for s in run["steps"]],
                         [("producer", "open")])
        self.assertTrue(run["tracks"][0]["status"].startswith("failed"))
        self.assertEqual([c["agent"] for c in self.call_log()], ["worker-a"])

    def test_a_crashing_agent_marks_its_step_error(self):
        self.write_recipe(recipe(gate=False))
        self.set_plan({"worker-a": [["crash", ""]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual(run["steps"][0]["status"], "error")
        kept = json.loads((self.root / ".harness" / "runs" / run["id"] /
                           run["steps"][0]["result_file"]).read_text())
        self.assertIn("fell over", kept["stderr_tail"])

    def test_without_a_gate_a_clean_run_finishes(self):
        self.write_recipe(recipe(gate=False))
        self.set_plan({"worker-a": [["produce", "T-901"]],
                       "verifier-a": [["approve", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual(run["status"], "finished")
        self.assertEqual(run["gate"]["status"], "none")

    def test_verify_first_starts_with_the_verifier(self):
        self.write_recipe(recipe())
        fr.launch(self.root, "demo", "enqueue")
        subprocess.run([sys.executable, ".harness/bin/blackboard.py", "claim", "T-901",
                        "--agent", "worker-a"], cwd=str(self.root), check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, ".harness/bin/blackboard.py", "handoff", "T-901",
                        "--to-role", "verifier", "--agent", "worker-a", "--note", "x"],
                       cwd=str(self.root), check=True, stdout=subprocess.DEVNULL)
        r = recipe()
        r["tracks"][0]["verify_first"] = True
        self.write_recipe(r)
        self.set_plan({"verifier-a": [["approve", "T-901"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual([s["role"] for s in run["steps"]], ["verifier"])
        self.assertEqual(run["tracks"][0]["status"], "done")

    def test_no_session_holder_is_registered(self):
        self.write_recipe(recipe(gate=False))
        self.set_plan({"worker-a": [["produce", "T-901"]],
                       "verifier-a": [["approve", "T-901"]]})
        fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertFalse((self.root / ".harness" / "session_holders.json").exists())
        kinds = [e["event"] for e in self.events()]
        self.assertIn("flow_step_started", kinds)
        self.assertIn("flow_step_ended", kinds)

    def test_two_tracks_run_side_by_side(self):
        r = recipe(gate=False)
        r["tracks"].append({"task": "T-903", "verify_task": "T-904", "producer": "worker-b",
                            "verifier": "verifier-b", "title": "other", "brief": "Other."})
        self.write_recipe(r)
        self.set_plan({"worker-a": [["produce", "T-901"]], "verifier-a": [["approve", "T-901"]],
                       "worker-b": [["produce", "T-903"]], "verifier-b": [["approve", "T-903"]]})
        run = fr.launch(self.root, "demo", "agents", foreground=True)
        self.assertEqual([t["status"] for t in run["tracks"]], ["done", "done"])
        self.assertEqual(len(run["steps"]), 4)


class TestGateAndStop(Fixture):
    def waiting_run(self):
        self.write_recipe(recipe())
        self.set_plan({"worker-a": [["produce", "T-901"]],
                       "verifier-a": [["approve", "T-901"]]})
        return fr.launch(self.root, "demo", "agents", foreground=True)

    def test_approve_once(self):
        run = self.waiting_run()
        out = fr.gate(self.root, run["id"], "approve", note="looks right")
        self.assertEqual(out["status"], "approved")
        self.assertEqual(out["gate"]["suite"]["counts"]["passed"], 7)
        with self.assertRaises(od.Refused):
            fr.gate(self.root, run["id"], "reject")

    def test_the_cli_gate_rejects(self):
        run = self.waiting_run()
        rc = fr.main(["--root", str(self.root), "gate", run["id"], "--reject",
                      "--note", "suite is red"])
        self.assertEqual(rc, 0)
        self.assertEqual(fr.read_run(self.root, run["id"])["status"], "rejected")

    def test_stop_marks_a_running_run_and_refuses_a_finished_one(self):
        run = self.waiting_run()
        with self.assertRaises(fr.Refused):
            fr.stop(self.root, run["id"])

        def as_running(r):
            r["status"] = "running"
            r["pid"] = None
            r["steps"].append({"track": "T-901", "role": "producer", "status": "running"})
        fr.update_run(self.root, run["id"], as_running)
        out = fr.stop(self.root, run["id"])
        self.assertEqual(out["status"], "stopped")
        self.assertEqual(out["steps"][-1]["status"], "stopped")
        self.assertFalse(out["signalled"])

    def test_bad_run_ids_are_refused(self):
        for bad in ("../x", "", ".."):
            with self.assertRaises(od.Refused):
                fr.read_run(self.root, bad)


if __name__ == "__main__":
    unittest.main()
