"""Tests for console.py (design T-484 sections 2, 6 and 8).

A real server on 127.0.0.1 and a free port, serving a throwaway root with copied harness
tools. Checks the Host check, the token, redaction, every GET shape, that no GET writes
anything, the event stream, and that every write goes through the harness's tools.
"""
import hashlib
import http.client
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
sys.path.insert(0, str(BIN_DIR))
import console  # noqa: E402
import flow_runner as fr  # noqa: E402

GET_ROUTES = {
    "/api/board": ["tasks", "counts"],
    "/api/locks": ["locks"],
    "/api/events": ["next", "events"],
    "/api/activity": ["agents"],
    "/api/society": ["roster", "forks", "cases", "precedents", "warrants", "acts", "problems"],
    "/api/decisions": ["decisions", "problems"],
    "/api/operator": ["decisions", "review", "gates", "signatures", "branch", "pending"],
    "/api/flows": ["flows"],
    "/api/flows/demo": ["recipe", "problems"],
    "/api/runs": ["runs"],
    "/api/charts/waves": ["waves"],
}

RECIPE = {"name": "demo", "description": "a demo", "tests": "changed", "gate": False,
          "tracks": [{"task": "T-901", "verify_task": "T-902", "producer": "worker-a",
                      "verifier": "verifier-a", "title": "build", "brief": "Build it."}]}


def tree_digest(root):
    """Every file's hash and every directory's name, so a new empty directory counts too."""
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            out[str(p.relative_to(root)) + "/"] = "dir"
    return out


class Server(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "repo"
        h = self.root / ".harness"
        h.mkdir(parents=True)
        shutil.copytree(str(BIN_DIR), str(h / "bin"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for d in ("tasks", "locks", "logs", "flows", "decisions", "rulings"):
            (h / d).mkdir()
        (h / "blackboard.json").write_text(json.dumps(
            {"schema_version": "0.1.0", "generation": 1, "tasks": {}, "announcements": []}))
        (h / "state.json").write_text(json.dumps({"limits": {}}))
        (h / "flows" / "demo.json").write_text(json.dumps(RECIPE))
        self.bb("add-task", "--id", "T-100", "--title", "a task", "--role", "worker")
        self.srv = console.ConsoleServer(self.root, port=0, poll=0.1, token="tok-123")
        self.port = self.srv.server_address[1]
        th = threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.05})
        th.daemon = True
        th.start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def bb(self, *args, agent="worker-x"):
        env = dict(os.environ)
        env["CLAUDE_HARNESS_AGENT_ID"] = agent
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        cp = subprocess.run([sys.executable, ".harness/bin/blackboard.py"] + list(args) +
                            ["--agent", agent], cwd=str(self.root), env=env,
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 0, cp.stderr)

    def request(self, method, path, body=None, headers=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        hdrs = {"Host": host or "127.0.0.1:{}".format(self.port)}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})
        conn.request(method, path, body=data, headers=hdrs)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            payload = json.loads(raw.decode())
        except ValueError:
            payload = raw.decode("utf-8", "replace")
        return r.status, payload, r

    def post(self, path, body, token="tok-123", method="POST"):
        return self.request(method, path, body, headers={"X-Console-Token": token})


class TestGuards(Server):
    def test_binds_loopback_only(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_a_foreign_host_header_is_refused(self):
        for host in ("evil.example", "evil.example:{}".format(self.port), "127.0.0.1:1"):
            status, body, _ = self.request("GET", "/api/board", host=host)
            self.assertEqual(status, 403, host)
        status, _, _ = self.request("GET", "/api/board", host="localhost:{}".format(self.port))
        self.assertEqual(status, 200)

    def test_writes_need_the_token(self):
        body = {"title": "new"}
        self.assertEqual(self.post("/api/tasks", body, token="")[0], 403)
        self.assertEqual(self.post("/api/tasks", body, token="nope")[0], 403)
        status, out, _ = self.post("/api/tasks", body)
        self.assertEqual(status, 200, out)

    def test_a_cross_site_origin_is_refused(self):
        status, _, _ = self.request("POST", "/api/tasks", {"title": "x"}, headers={
            "X-Console-Token": "tok-123", "Origin": "http://evil.example"})
        self.assertEqual(status, 403)

    def test_writes_must_be_json(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/tasks", body="title=x", headers={
            "Host": "127.0.0.1:{}".format(self.port), "X-Console-Token": "tok-123",
            "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(conn.getresponse().status, 415)
        conn.close()

    def test_the_page_carries_the_token_and_strict_headers(self):
        status, html, r = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn('content="tok-123"', html)
        self.assertNotIn(console.TOKEN_PLACEHOLDER, html)
        csp = r.getheader("Content-Security-Policy")
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")

    def test_key_material_is_never_served(self):
        keys = self.root / ".harness" / "keys"
        keys.mkdir()
        (keys / "agent.json").write_text('{"secret": "KEY-MATERIAL-123"}')
        for bad in ("/ui/../keys/agent.json", "/ui/%2e%2e/keys/agent.json",
                    "/ui/..%2fkeys%2fagent.json", "/.harness/keys/agent.json",
                    "/keys/agent.json", "/api/../keys/agent.json"):
            status, body, _ = self.request("GET", bad)
            self.assertEqual(status, 404, bad)
            self.assertNotIn("KEY-MATERIAL-123", json.dumps(body), bad)

    def test_static_files_stay_inside_the_ui_folder(self):
        self.assertEqual(self.request("GET", "/ui/app.js")[0], 200)
        for bad in ("/ui/../bin/console.py", "/ui/%2e%2e/bin/console.py",
                    "/ui/..%2fbin%2fconsole.py", "/ui/", "/ui/i18n/../../blackboard.json",
                    "/ui/README.md"):
            self.assertEqual(self.request("GET", bad)[0], 404, bad)


class TestReads(Server):
    def test_every_get_has_its_shape(self):
        for path, keys in GET_ROUTES.items():
            status, body, _ = self.request("GET", path)
            self.assertEqual(status, 200, (path, body))
            for k in keys:
                self.assertIn(k, body, path)
        self.assertEqual(self.request("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.request("GET", "/api/runs/no-such-run")[0], 404)
        self.assertEqual(self.request("GET", "/api/events?since=x")[0], 400)

    def test_no_get_writes_anything(self):
        before = tree_digest(self.root)
        for path in list(GET_ROUTES) + ["/", "/ui/app.js", "/api/events?since=0"]:
            self.request("GET", path)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/stream", headers={"Host": "127.0.0.1:{}".format(self.port)})
        r = conn.getresponse()
        r.fp.readline()
        conn.close()
        self.assertEqual(tree_digest(self.root), before)

    def test_the_board_lists_tasks_with_counts(self):
        _, body, _ = self.request("GET", "/api/board")
        self.assertEqual([t["id"] for t in body["tasks"]], ["T-100"])
        self.assertEqual(body["counts"], {"open": 1})

    def test_events_follow_an_offset(self):
        first = self.request("GET", "/api/events")[1]
        self.bb("claim", "T-100")
        after = self.request("GET", "/api/events?since={}".format(first["next"]))[1]
        self.assertTrue(any(e.get("event") == "task_claimed" for e in after["events"]))
        self.assertGreater(after["next"], first["next"])

    def test_activity_names_the_claimant_and_its_last_act(self):
        self.bb("claim", "T-100", agent="worker-z")
        _, body, _ = self.request("GET", "/api/activity")
        a = [x for x in body["agents"] if x["name"] == "worker-z"][0]
        self.assertEqual(a["task"], "T-100")
        self.assertEqual(a["last_action"]["event"], "task_claimed")


class TestRedaction(Server):
    def test_home_user_and_temp_paths_are_redacted(self):
        home = str(pathlib.Path.home())
        private_tmp = "/pri" + "vate/tm" + "p"  # in pieces, so this file holds no temp path
        folders = "/va" + "r/fol" + "ders"
        out = console.redact({"a": home + "/x", "b": [tempfile.gettempdir() + "/y"],
                              "c": private_tmp + "/z and " + folders + "/ab/T/q"})
        text = json.dumps(out)
        self.assertNotIn(home, text)
        self.assertIn("~/x", text)
        self.assertNotIn(private_tmp, text)
        self.assertNotIn(folders, text)

    def test_every_get_route_is_redacted(self):
        home = str(pathlib.Path.home())
        self.bb("add-task", "--id", "T-200", "--title", "look in " + home + "/notes",
                "--role", "worker")
        self.bb("claim", "T-200", agent="worker-h")
        with open(str(self.root / ".harness" / "logs" / "events.jsonl"), "a") as fh:
            fh.write(json.dumps({"ts": "2026-11-18T00:00:00Z", "event": "task_claimed",
                                 "agent": "worker-h", "task": "T-200",
                                 "path": home + "/a.txt"}) + "\n")
        for path in list(GET_ROUTES) + ["/api/events?since=0"]:
            _, body, _ = self.request("GET", path)
            self.assertNotIn(home, json.dumps(body), path)

    def test_api_answers_are_redacted(self):
        home = str(pathlib.Path.home())
        with open(str(self.root / ".harness" / "logs" / "events.jsonl"), "a") as fh:
            fh.write(json.dumps({"ts": "2026-11-18T00:00:00Z", "event": "probe",
                                 "agent": "a", "path": home + "/secret.txt"}) + "\n")
        _, body, _ = self.request("GET", "/api/events?since=0")
        text = json.dumps(body)
        self.assertNotIn(home, text)
        self.assertIn("~/secret.txt", text)


class TestStream(Server):
    def test_new_events_and_board_changes_arrive(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/stream", headers={"Host": "127.0.0.1:{}".format(self.port)})
        r = conn.getresponse()
        self.assertEqual(r.getheader("Content-Type").split(";")[0], "text/event-stream")
        time.sleep(0.3)
        self.bb("claim", "T-100")
        seen, deadline = set(), time.time() + 8
        while time.time() < deadline and not {"events", "changed"} <= seen:
            line = r.fp.readline().decode()
            if line.startswith("event: "):
                seen.add(line.strip()[7:])
        conn.close()
        self.assertEqual(seen & {"events", "changed"}, {"events", "changed"})


    def test_streamed_events_are_redacted(self):
        home = str(pathlib.Path.home())
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/stream", headers={"Host": "127.0.0.1:{}".format(self.port)})
        r = conn.getresponse()
        time.sleep(0.3)
        with open(str(self.root / ".harness" / "logs" / "events.jsonl"), "a") as fh:
            fh.write(json.dumps({"ts": "2026-11-18T00:00:00Z", "event": "probe",
                                 "agent": "a", "path": home + "/streamed.txt"}) + "\n")
        data, deadline = "", time.time() + 8
        while time.time() < deadline and "streamed.txt" not in data:
            line = r.fp.readline().decode()
            if line.startswith("data: "):
                data += line
        conn.close()
        self.assertIn("~/streamed.txt", data)
        self.assertNotIn(home, data)


class TestWrites(Server):
    def board(self):
        return json.loads((self.root / ".harness" / "blackboard.json").read_text())["tasks"]

    def test_add_task_goes_through_the_blackboard_as_operator(self):
        status, out, _ = self.post("/api/tasks", {"title": "from the page", "epic": "e1",
                                                  "depends_on": "T-100"})
        self.assertEqual(status, 200, out)
        tid = out["result"]["id"]
        self.assertEqual(tid, "T-101")
        task = self.board()[tid]
        self.assertEqual(task["depends_on"], ["T-100"])
        events = (self.root / ".harness" / "logs" / "events.jsonl").read_text()
        self.assertIn('"agent": "operator"', events)

    def test_a_leak_in_a_task_is_refused(self):
        status, out, _ = self.post("/api/tasks", {"title": "see /Us" + "ers/jdoe/x"})
        self.assertEqual(status, 409)
        self.assertEqual(sorted(self.board()), ["T-100"])

    def test_operator_verdict_only_on_a_task_in_review(self):
        self.assertEqual(self.post("/api/tasks/T-100/verdict", {"outcome": "done"})[0], 409)
        self.bb("claim", "T-100")
        self.bb("handoff", "T-100", "--to-role", "verifier", "--note", "built")
        status, out, _ = self.post("/api/tasks/T-100/verdict", {"outcome": "done", "note": "ok"})
        self.assertEqual(status, 200, out)
        self.assertEqual(self.board()["T-100"]["status"], "done")

    def test_ruling_writes_one_new_record(self):
        card = {"id": "D-001", "title": "t", "question": "q?", "recommendation": "yes",
                "if_yes": "a", "if_no": "b", "options": ["yes", "no"], "blocks": [],
                "status": "open", "created": "2026-11-18"}
        (self.root / ".harness" / "decisions" / "D-001.json").write_text(json.dumps(card))
        status, out, _ = self.post("/api/decisions/D-001/rule", {"choice": "yes"})
        self.assertEqual(status, 200, out)
        rec = json.loads((self.root / ".harness" / "rulings" / "R-001.json").read_text())
        self.assertEqual((rec["choice"], rec["via"]), ("yes", "console"))
        self.assertEqual(self.post("/api/decisions/D-001/rule", {"choice": "no"})[0], 409)

    def test_a_recipe_is_validated_before_it_is_saved(self):
        bad = dict(RECIPE, name="other", tests="everything")
        status, _, _ = self.post("/api/flows/other", {"recipe": bad}, method="PUT")
        self.assertEqual(status, 409)
        self.assertFalse((self.root / ".harness" / "flows" / "other.json").exists())
        good = dict(RECIPE, name="other")
        status, out, _ = self.post("/api/flows/other", {"recipe": good}, method="PUT")
        self.assertEqual(status, 200, out)
        self.assertTrue((self.root / ".harness" / "flows" / "other.json").exists())
        _, res, _ = self.post("/api/flows/other/validate", {"recipe": bad})
        self.assertTrue(res["result"]["problems"])

    def test_launch_enqueue_and_gate_through_the_page(self):
        status, out, _ = self.post("/api/flows/demo/launch", {"mode": "enqueue"})
        self.assertEqual(status, 200, out)
        self.assertEqual(out["result"]["status"], "enqueued")
        self.assertIn("T-901", self.board())
        run_id = out["result"]["id"]
        self.assertEqual(self.post("/api/runs/{}/gate".format(run_id),
                                   {"decision": "approve"})[0], 409)

        def waiting(r):
            r["status"] = "awaiting_operator"
            r["gate"] = {"status": "pending", "suite": {"summary": "1 passed"}}
        fr.update_run(self.root, run_id, waiting)
        _, op, _ = self.request("GET", "/api/operator")
        self.assertEqual([g["id"] for g in op["gates"]], [run_id])
        status, out, _ = self.post("/api/runs/{}/gate".format(run_id),
                                   {"decision": "approve", "note": "fine"})
        self.assertEqual(status, 200, out)
        self.assertEqual(fr.read_run(self.root, run_id)["gate"]["via"], "console")

    def test_unknown_write_routes_are_404(self):
        self.assertEqual(self.post("/api/blackboard", {})[0], 404)
        self.assertEqual(self.post("/api/flows/demo", {"recipe": RECIPE})[0], 404)


if __name__ == "__main__":
    unittest.main()
