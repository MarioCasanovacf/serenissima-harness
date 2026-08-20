import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / ".harness" / "bin" / "gemini_headless_runner.py"

def load_runner():
    """Import the runner as a module so the signal path can be tested without a machine
    that happens to be misbehaving. The EPERM below was observed, not imagined -- 2 of 25
    loaded runs -- but nothing reproduces it on demand, and an unreproducible defect still
    needs a regression test."""
    spec = importlib.util.spec_from_file_location("gemini_headless_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SILENT_HANGING_SH = """\
#!/bin/sh
sleep 60 &
if [ -n "${FAKE_GEMINI_DESCENDANT_PID}" ]; then
    printf '%s' "$!" > "${FAKE_GEMINI_DESCENDANT_PID}"
fi
sleep 60
"""
"""A silent process holding one live descendant, registered as fast as POSIX allows.

THIS USED TO BE A PYTHON SCRIPT AND THAT IS WHY THE REAPING TEST WAS FLAKY. The
descendant is only observable once the fake has written its pid, and that write happens
INSIDE the runner's wall-clock budget: the runner starts its clock immediately before
`Popen`, so every millisecond the fake spends booting is spent out of the budget. A
Python fake spends a whole interpreter startup there. Measured on this machine, idle,
12 runs, spawn -> pid file, 2026-08-19:

    min 0.201 s   median 0.286 s   p90 0.331 s   max 0.545 s

Against the 0.35 s budget the test used, that is a coin flip: 4 of 10 runs never
registered the descendant and the test then died reading a missing pid file, which
reads as a broken test rather than a lost race. `$!` costs a fork, not an interpreter,
so on an idle machine registration lands two orders of magnitude inside the budget.

A SHELL FAKE IS NOT ENOUGH ON ITS OWN. Measured again with 8 CPU burners and 6 copies
of this suite in parallel, the shell fake ALSO lost 6 of 6 times: under saturation even
fork+exec is not schedulable inside 0.35 s. That is why the reaping claim now sizes its
budget from a live measurement instead of a constant -- see `register_latency_seconds`.
"""


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

    def silent_hanging_gemini(self, workspace=None):
        executable = (workspace or self.workspace) / "fake-gemini-silent-hang"
        executable.write_text(SILENT_HANGING_SH, encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def register_latency_seconds(self, ceiling=30.0):
        """Time THIS machine, RIGHT NOW, from spawn to a registered descendant.

        The reaping claim below cannot be asserted against a constant. The quantity the
        budget has to cover is a fork+exec plus a fork under whatever load the machine
        happens to be carrying, and that ranges over two orders of magnitude between an
        idle laptop and a saturated one. So the test measures it, seconds before it needs
        it, on the same fake binary the run will use.

        THE PROBE DOES NOT GO THROUGH THE RUNNER, and that is the point: the runner's own
        interpreter startup is spent BEFORE its clock starts and is therefore not charged
        to the budget at all. Including it would measure the wrong thing. What is left is
        exactly the in-clock cost, which is why the caller multiplies rather than trusts
        the raw figure.

        The probe gets its own session so the kill below cannot reach the test runner's
        process group. An earlier version of this helper killed pytest.
        """
        with tempfile.TemporaryDirectory() as scratch:
            probe = Path(scratch)
            binary = self.silent_hanging_gemini(workspace=probe)
            pid_file = probe / "probe.pid"
            env = os.environ.copy()
            env["FAKE_GEMINI_DESCENDANT_PID"] = str(pid_file)
            started = time.monotonic()
            process = subprocess.Popen(
                [str(binary)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=(os.name == "posix"),
            )
            try:
                deadline = started + ceiling
                while not pid_file.is_file() and time.monotonic() < deadline:
                    time.sleep(0.005)
                registered = pid_file.is_file()
                latency = time.monotonic() - started
            finally:
                self.reap(process, pid_file)
            self.assertTrue(
                registered,
                "the probe could not register a descendant in %s s; this machine cannot "
                "run the process-group assertion at all, and no budget would fix it"
                % ceiling,
            )
            return latency

    def reap(self, process, pid_file=None):
        """Leave no probe process behind, whatever went wrong above."""
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        else:  # pragma: no cover - the suite skips the POSIX assertions elsewhere
            process.kill()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            pass
        if pid_file is not None and pid_file.is_file():
            try:
                os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, ValueError):
                pass

    def invoke(self, binary, *extra, env=None, timeout=10):
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
            timeout=timeout,
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

    def test_wall_clock_timeout_blocks_a_silent_child_and_preserves_exit_124(self):
        """The timeout semantics, with NOTHING riding on the child being schedulable.

        This half of the old test was never flaky and never could be: the runner reaches
        its own deadline whether or not the fake ever got as far as running a line. It
        keeps the short constant budget, so the suite keeps paying 0.35 s for it.
        """
        started = time.monotonic()
        result = self.invoke(self.silent_hanging_gemini(), "--timeout-seconds", "0.35")
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

    @unittest.skipUnless(os.name == "posix", "process-group assertion requires POSIX")
    def test_timeout_reaps_the_whole_process_group_including_descendants(self):
        """The reaping claim, on a budget measured instead of assumed.

        SPLIT OUT OF THE TIMEOUT TEST ON PURPOSE. Fused together, a semantics assertion
        that cannot fail was held hostage by a spawn race that fails under load, and the
        combined failure was misread twice -- once as a timing regression, once as a
        broken fixture. Separated, each claim fails for its own reason.

        A descendant that never registered is not a reaping that passed. The measured
        latency is multiplied by 4 and floored at 0.5 s; the ceiling is 3.0 s because the
        runner spends up to two grace periods on top of the budget and the whole call has
        to stay inside its own subprocess timeout.
        """
        latency = self.register_latency_seconds()
        budget = round(min(3.0, max(0.5, latency * 6)), 3)

        pid_file = self.workspace / "descendant.pid"
        env = os.environ.copy()
        env["FAKE_GEMINI_DESCENDANT_PID"] = str(pid_file)
        result = self.invoke(
            self.silent_hanging_gemini(),
            "--timeout-seconds",
            str(budget),
            env=env,
            timeout=budget + 8,
        )

        self.assertEqual(result.returncode, 124, result.stderr)
        _, summary = self.only_summary()
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["blocked_reason"], "wall_clock_timeout")
        self.assertEqual(summary["wall_clock_timeout_seconds"], budget)
        self.assertGreaterEqual(summary["elapsed_seconds"], budget - 0.05)

        # A bare FileNotFoundError here has already been misdiagnosed once as a timing
        # assertion, so the failure says which claim went unmeasured and on what evidence.
        self.assertTrue(
            pid_file.is_file(),
            "the descendant never registered inside a %s s budget sized from a %.3f s "
            "measurement taken moments earlier; the runner's reaping is UNMEASURED here, "
            "and this is not a timeout regression" % (budget, latency),
        )
        descendant = int(pid_file.read_text(encoding="utf-8"))

        # SIGKILL IS DELIVERED, NOT COMPLETED. The descendant's parent is dead, so the
        # descendant is reparented and reaped by launchd, and `kill(pid, 0)` keeps
        # succeeding for a zombie in the meantime. Asserting instant disappearance failed
        # 3 of 8 loaded runs while the reaping itself was working correctly. What the
        # runner owes is that the descendant does not OUTLIVE the run; the poll asserts
        # exactly that and nothing about the scheduler's punctuality.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                os.kill(descendant, 0)
            except ProcessLookupError:
                return
            time.sleep(0.02)
        self.fail(
            "the descendant %s outlived the run by more than 10 s; refused signals "
            "recorded by the runner: %r" % (descendant, summary.get("termination_refused"))
        )

    def test_non_turn_limit_exit_code_is_preserved(self):
        result = self.invoke(self.fake_gemini(42))
        self.assertEqual(result.returncode, 42)
        _, summary = self.only_summary()
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["exit_code"], 42)
        self.assertNotIn("blocked_reason", summary)

    def test_a_refused_kill_is_written_down_and_silence_means_it_was_accepted(self):
        """Absorbing a refusal is not the same as pretending it did not happen.

        A refused SIGKILL means the process group may have outlived the run. The field is
        absent on the ordinary path so that its presence carries information.
        """
        runner = load_runner()
        self.assertEqual(runner.record_refusals({}, []), {})
        refused = [{"signal": "SIGKILL", "error": "[Errno 1] Operation not permitted"}]
        self.assertEqual(
            runner.record_refusals({}, refused), {"termination_refused": refused}
        )

        result = self.invoke(self.silent_hanging_gemini(), "--timeout-seconds", "0.35")
        self.assertEqual(result.returncode, 124, result.stderr)
        _, summary = self.only_summary()
        # ESRCH on the second signal is the ordinary outcome -- SIGTERM already worked --
        # and it is NOT a refusal. Recording it would have marked almost every timed-out
        # run and drained the field of meaning.
        self.assertNotIn("termination_refused", summary)

    def test_an_absent_binary_fails_the_preflight_and_writes_no_run_at_all(self):
        """Missing and unlaunchable are two different failures and only one of them
        reaches the launch-error path. Neither had a test before this pair."""
        missing = self.workspace / "not-installed-gemini"
        result = self.invoke(missing)
        self.assertEqual(result.returncode, 127)
        self.assertIn("executable not found", result.stderr)
        self.assertFalse((self.workspace / ".harness" / "logs" / "gemini").exists())

    def test_a_binary_that_cannot_be_executed_is_reported_as_a_launch_error(self):
        """Present, executable, and still impossible to exec: a shebang pointing nowhere.
        This is the only way into the launch-error branch, which had no test at all."""
        unlaunchable = self.workspace / "fake-gemini-bad-interpreter"
        unlaunchable.write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
        unlaunchable.chmod(0o755)
        result = self.invoke(unlaunchable)
        self.assertEqual(result.returncode, 127)
        _, summary = self.only_summary()
        self.assertEqual(summary["status"], "launch_error")
        self.assertFalse(summary["child_launched"])
        self.assertIn("launch_error", summary)
        self.assertNotIn("runner_error", summary)

    @unittest.skipUnless(os.name == "posix", "signal semantics are POSIX-only")
    def test_a_refused_kill_does_not_escape_and_cannot_be_filed_as_a_launch_error(self):
        """DEFECT RUNNER-LAUNCH-MISREPORT-A.

        PermissionError is an OSError. Before the fix it escaped `terminate_process_group`,
        unwound the whole run, and was written down as a CLI that never started -- for a
        run that had launched, streamed and timed out exactly as designed. The signal is
        refused here on purpose; what is asserted is that nothing propagates.
        """
        runner = load_runner()
        self.assertIn(PermissionError, runner.UNSIGNALLABLE)
        killed, refused = self.refuse_every_signal(runner, alive=True)

        # Both signals were attempted and both were swallowed: a refused kill must not
        # abort the run, and it must not stop the escalation to SIGKILL either.
        self.assertEqual([sig for _, sig in killed], [signal.SIGTERM, signal.SIGKILL])
        # The leader was still alive, so both refusals carry information and are kept.
        self.assertEqual([entry["signal"] for entry in refused], ["SIGTERM", "SIGKILL"])

    @unittest.skipUnless(os.name == "posix", "signal semantics are POSIX-only")
    def test_a_refusal_on_a_leader_that_already_exited_is_not_a_refusal(self):
        """Darwin answers `killpg` on an emptied group with EPERM instead of ESRCH.

        Observed under load in a summary that also carried `child_exit_code: -15` -- the
        leader had been reaped by SIGTERM and the follow-up SIGKILL still came back
        "Operation not permitted". Recording that claims the group may have survived when
        the leader's own exit status proves otherwise, and it put the field on a run where
        nothing went wrong.
        """
        runner = load_runner()
        killed, refused = self.refuse_every_signal(runner, alive=False)
        self.assertEqual([sig for _, sig in killed], [signal.SIGTERM, signal.SIGKILL])
        self.assertEqual(refused, [])

    def refuse_every_signal(self, runner, alive):
        killed = []

        class Leader:
            pid = 4242

            def poll(self):
                return None if alive else -15

            def wait(self, timeout=None):
                return 0

            def terminate(self):  # pragma: no cover - POSIX takes the killpg branch
                pass

            def kill(self):  # pragma: no cover - POSIX takes the killpg branch
                pass

        def refusing_killpg(pgid, sig):
            killed.append((pgid, sig))
            raise PermissionError(1, "Operation not permitted")

        original = os.killpg
        os.killpg = refusing_killpg
        try:
            refused = runner.terminate_process_group(Leader())
        finally:
            os.killpg = original
        return killed, refused

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
