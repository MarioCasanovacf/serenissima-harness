import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / ".harness" / "bin" / "gemini_headless_runner.py"


class GeminiHeadlessRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        (self.workspace / ".harness").mkdir()
        self.prompt = self.workspace / "prompt with spaces.md"
        self.prompt.write_text("Do the work; touch /tmp/nope && echo unsafe\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def fake_gemini(self, exit_code=0):
        executable = self.workspace / ("fake-gemini-%s" % exit_code)
        executable.write_text(
            textwrap.dedent(
                """\
                #!{python}
                import json
                import sys

                assert "--output-format" in sys.argv
                assert sys.argv[sys.argv.index("--output-format") + 1] == "stream-json"
                assert "--yolo" not in sys.argv
                assert "--approval-mode=yolo" not in sys.argv
                prompt = sys.argv[sys.argv.index("--prompt") + 1]
                assert "touch /tmp/nope && echo unsafe" in prompt
                print(json.dumps({{"type": "init", "session_id": "session-1", "model": "gemini-test"}}), flush=True)
                print(json.dumps({{"type": "message", "role": "assistant", "content": "working"}}), flush=True)
                print(json.dumps({{"type": "result", "stats": {{"total_tokens": 12}}}}), flush=True)
                raise SystemExit({exit_code})
                """
            ).format(python=sys.executable, exit_code=exit_code),
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def silent_hanging_gemini(self):
        executable = self.workspace / "fake-gemini-silent-hang"
        executable.write_text(
            textwrap.dedent(
                """\
                #!{python}
                import os
                import subprocess
                import sys
                import time

                pid_file = os.environ.get("FAKE_GEMINI_DESCENDANT_PID")
                child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
                if pid_file:
                    with open(pid_file, "w", encoding="utf-8") as handle:
                        handle.write(str(child.pid))
                time.sleep(60)
                """
            ).format(python=sys.executable),
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def invoke(self, binary, *extra, env=None):
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--prompt-file",
                str(self.prompt),
                "--agent-id",
                "gemini-worker:1",
                "--task-id",
                "TASK-007",
                "--gemini-bin",
                str(binary),
                "--cwd",
                str(self.workspace),
                *extra,
            ],
            text=True,
            capture_output=True,
            env=env,
            timeout=10,
        )

    def only_summary(self):
        summaries = list((self.workspace / ".harness" / "logs" / "gemini").glob("*/*/summary.json"))
        self.assertEqual(len(summaries), 1)
        return summaries[0], json.loads(summaries[0].read_text(encoding="utf-8"))

    def test_success_streams_and_captures_jsonl_with_compact_summary(self):
        result = self.invoke(self.fake_gemini())
        self.assertEqual(result.returncode, 0, result.stderr)
        streamed = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([event["type"] for event in streamed], ["init", "message", "result"])

        summary_path, summary = self.only_summary()
        raw = summary_path.parent / "events.jsonl"
        self.assertEqual(raw.read_text(encoding="utf-8"), result.stdout)
        self.assertEqual(summary["status"], "succeeded")
        self.assertEqual(summary["event_counts"], {"init": 1, "message": 1, "result": 1})
        self.assertEqual(summary["session_id"], "session-1")
        self.assertEqual(summary["stats"], {"total_tokens": 12})
        self.assertNotIn("touch /tmp/nope", json.dumps(summary))

    def test_turn_limit_is_blocked_and_exit_53_is_preserved(self):
        result = self.invoke(self.fake_gemini(53))
        self.assertEqual(result.returncode, 53)
        _, summary = self.only_summary()
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["blocked_reason"], "turn_limit_exceeded")
        self.assertEqual(summary["exit_code"], 53)

    @unittest.skipUnless(os.name == "posix", "process-group assertion requires POSIX")
    def test_wall_clock_timeout_bounds_silent_child_and_reaps_process_group(self):
        pid_file = self.workspace / "descendant.pid"
        env = os.environ.copy()
        env["FAKE_GEMINI_DESCENDANT_PID"] = str(pid_file)
        started = time.monotonic()
        result = self.invoke(
            self.silent_hanging_gemini(), "--timeout-seconds", "0.35", env=env
        )
        elapsed = time.monotonic() - started

        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(elapsed, 5)
        _, summary = self.only_summary()
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["blocked_reason"], "wall_clock_timeout")
        self.assertEqual(summary["exit_code"], 124)
        self.assertEqual(summary["wall_clock_timeout_seconds"], 0.35)
        self.assertGreaterEqual(summary["elapsed_seconds"], 0.3)
        self.assertLess(summary["elapsed_seconds"], 5)

        descendant = int(pid_file.read_text(encoding="utf-8"))
        with self.assertRaises(ProcessLookupError):
            os.kill(descendant, 0)

    def test_non_turn_limit_exit_code_is_preserved(self):
        result = self.invoke(self.fake_gemini(42))
        self.assertEqual(result.returncode, 42)
        _, summary = self.only_summary()
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["exit_code"], 42)
        self.assertNotIn("blocked_reason", summary)

    def test_dry_run_needs_no_installed_dependency_and_writes_nothing(self):
        missing = self.workspace / "missing;gemini"
        result = self.invoke(missing, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertFalse(plan["dependency"]["available"])
        self.assertFalse(plan["uses_shell"])
        self.assertFalse(plan["yolo"])
        state = json.loads((ROOT / ".harness" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            plan["wall_clock_timeout_seconds"],
            state["limits"]["max_seconds_per_command"],
        )
        self.assertNotIn("touch /tmp/nope", result.stdout)
        self.assertFalse((self.workspace / ".harness" / "logs" / "gemini").exists())

    def test_discovery_does_not_require_run_arguments(self):
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--discover", "--gemini-bin", str(self.fake_gemini())],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["available"])

    def test_invalid_identity_is_input_error_before_execution(self):
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--prompt-file",
                str(self.prompt),
                "--agent-id",
                "bad\n--yolo",
                "--task-id",
                "TASK-007",
                "--gemini-bin",
                str(self.fake_gemini()),
                "--cwd",
                str(self.workspace),
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 42)
        self.assertIn("input error", result.stderr)

    def test_timeout_must_be_positive(self):
        result = self.invoke(self.fake_gemini(), "--timeout-seconds", "0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a finite number greater than zero", result.stderr)

        result = self.invoke(self.fake_gemini(), "--timeout-seconds", "nan")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a finite number greater than zero", result.stderr)


if __name__ == "__main__":
    unittest.main()
