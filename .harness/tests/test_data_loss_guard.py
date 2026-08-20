import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / ".harness" / "bin" / "prevent_data_loss.py"
SAFE_DELETE = ROOT / ".harness" / "bin" / "safe_delete.py"


def run_guard(workspace: Path, command: str, tool_name="exec_command"):
    payload = {
        "session_id": "test-session",
        "cwd": str(workspace),
        "tool_name": tool_name,
        "tool_input": {"cmd": command},
    }
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )


class DataLossGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        (self.workspace / ".harness" / "logs").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def assertBlocked(self, command, tool_name="exec_command"):
        marker = self.workspace / "valuable.txt"
        marker.write_text("preserve me", encoding="utf-8")
        result = run_guard(self.workspace, command, tool_name)
        self.assertEqual(result.returncode, 2, (command, result.stderr))
        self.assertIn("DATA-LOSS GUARD", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me")
        events = (self.workspace / ".harness" / "logs" / "events.jsonl").read_text().splitlines()
        event = json.loads(events[-1])
        self.assertEqual(event["event"], "data_loss_action_blocked")

    def test_blocks_system_card_examples(self):
        for command in (
            "rm -rf project",
            "git clean -xfd",
            "git reset --hard HEAD",
            "git push origin main --force",
            "git push -f origin main",
            "git -C repo clean -fdx",
            "sudo git -C repo reset --hard HEAD",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_blocks_edit_discard_and_filesystem_tools(self):
        for command in (
            "git checkout -- src/app.py",
            "git checkout -f feature",
            "git restore src/app.py",
            "find . -name '*.tmp' -delete",
            "unlink notes.txt",
            "rmdir old-project",
            "shred -u secret.txt",
            "truncate -s 0 data.db",
            "printf '%s\\0' cache | xargs -0 rm -rf",
            "bash -c 'rm -rf project'",
            "/bin/rm -rf project",
            "env rm -rf project",
            "/usr/bin/env rm -rf project",
            "nice rm -rf project",
            "nohup rm -rf project",
            "git switch --discard-changes feature",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_blocks_language_one_liners(self):
        for command in (
            "python3 -c \"import shutil; shutil.rmtree('project')\"",
            "python3 -c \"import os; os.unlink('data')\"",
            "python3 -c \"import subprocess; subprocess.run(['rm', '-rf', 'project'])\"",
            "python3 -c \"import os; os.system('rm -rf project')\"",
            "python3 -c \"from pathlib import Path; Path('data').unlink()\"",
            "node -e \"require('fs').rmSync('project', {recursive:true})\"",
            "go run cleanup.go  # os.RemoveAll(path)",
            "ruby -e \"FileUtils.rm_rf('project')\"",
            "perl -e \"unlink 'data'\"",
            "powershell -Command \"Remove-Item -Recurse project\"",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_blocks_apply_patch_delete_file(self):
        payload = {
            "cwd": str(self.workspace),
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n*** Delete File: valuable.txt\n*** End Patch"},
        }
        marker = self.workspace / "valuable.txt"
        marker.write_text("still here")
        result = subprocess.run(
            [sys.executable, str(GUARD)], input=json.dumps(payload), text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertTrue(marker.exists())

    def test_blocks_find_exec_rm(self):
        for command in (
            r"find . -exec rm {} \;",
            "find . -exec rm -rf {} +",
            r"find . -execdir rm -rf {} \;",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_blocks_backslash_escaped_rm(self):
        for command in (
            r"\rm -rf foo",
            r"\rm -rf foo; echo done",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_blocks_git_rm_without_cached(self):
        for command in (
            "git rm -rf vendor",
            "git rm vendor/lib.js",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_allows_git_rm_cached(self):
        result = run_guard(self.workspace, "git rm --cached foo")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_allows_non_destructive_commands(self):
        for command in (
            "git status --short",
            "git diff --check",
            "git checkout feature-branch",
            "python3 -m unittest discover .harness/tests",
            "rg --files",
            "rm --help",
            "find . -name '*.tmp' -print",
            "git rm --cached foo",
        ):
            with self.subTest(command=command):
                result = run_guard(self.workspace, command)
                self.assertEqual(result.returncode, 0, (command, result.stderr))

    def test_malformed_payload_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, str(GUARD)], input="not-json", text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0)


# --------------------------------------------------------------------------- T-407

# BRAZO A de la matriz: toda forma destructiva que la implementacion de regex bloqueaba,
# ENUMERADA DESDE ESA IMPLEMENTACION y verificada bloqueada contra ella antes de tocarla,
# mas las formas que el parseo mismo podria haber abierto.
STILL_BLOCKED = (
    "git clean -xfd", "git -C repo clean -fdx", "sudo git clean -f",
    "git reset --hard HEAD", "sudo git -C repo reset --hard HEAD",
    "git push origin main --force", "git push -f origin main",
    "git push --force-with-lease origin main",
    "git checkout -- src/app.py", "git checkout -f feature", "git checkout --ours f",
    "git restore src/app.py", "git switch --discard-changes feature",
    "git rm -rf vendor", "git rm vendor/lib.js",
    "find . -name '*.tmp' -delete", "find . -exec rm {} \\;",
    "find . -exec rm -rf {} +", "find . -execdir rm -rf {} \\;",
    "env rm -rf project", "/usr/bin/env rm -rf project", "nice rm -rf project",
    "nohup rm -rf project", "bash -c 'rm -rf project'", 'sh -c "rm -rf project"',
    "sudo rm -rf project", "command rm -rf project", "busybox rm -rf project",
    "rm -rf project", "rm file.txt", "/bin/rm -rf project", "\\rm -rf foo",
    "\\rm -rf foo; echo done", "echo hola && rm -rf project",
    "printf '%s\\0' cache | xargs -0 rm -rf", "ls | xargs rm",
    "unlink notes.txt", "rmdir old-project", "shred -u secret.txt",
    "truncate -s 0 data.db",
    'powershell -Command "Remove-Item -Recurse project"', "del archivo.txt",
    "erase archivo.txt",
    'python3 -c "import shutil; shutil.rmtree(\'project\')"',
    'python3 -c "import os; os.unlink(\'data\')"',
    'python3 -c "import os; os.remove(\'data\')"',
    'python3 -c "import os; os.rmdir(\'data\')"',
    'python3 -c "import os; os.removedirs(\'data\')"',
    'python3 -c "import subprocess; subprocess.run([\'rm\', \'-rf\', \'project\'])"',
    'python3 -c "import os; os.system(\'rm -rf project\')"',
    'python3 -c "from pathlib import Path; Path(\'data\').unlink()"',
    'node -e "require(\'fs\').rmSync(\'project\', {recursive:true})"',
    'node -e "fs.promises.unlink(\'x\')"',
    "go run cleanup.go  # os.RemoveAll(path)",
    'ruby -e "FileUtils.rm_rf(\'project\')"',
    'perl -e "unlink \'data\'"',
)

OPENED_BY_PARSING = (
    "bash <<'EOF'\nrm -rf project\nEOF",
    "sh <<EOF\ngit clean -xfd\nEOF",
    "python3 - <<'PY'\nimport shutil; shutil.rmtree('project')\nPY",
    "sudo env nice rm -rf project",
    "timeout 5 rm -rf project",
    "xargs -0 rm -rf < lista",
    "true && sudo rm -rf project",
    "FOO=bar rm -rf project",
)

# BRAZO B: las reproducciones. Prosa que DESCRIBE una remocion sin realizarla.
PROSE_THAT_MUST_PASS = (
    'python3 .harness/bin/attest.py sign --name x --key k --kind commit '
    '--body "la guarda bloquea rm -rf, git clean -xfd y git reset --hard"',
    "cat > nota.md <<'TXT'\nEl defecto: la guarda bloqueo rm -rf project.\nTXT",
    "cat > nota.md <<'TXT'\nUna prueba AST prohibe llamar shutil.rmtree, os.remove y "
    "Path(x).unlink().\nTXT",
    'python3 .harness/bin/blackboard.py update T-1 --note "hay que evitar git reset --hard"',
    'echo "el corpus incluye rm -rf project y find . -delete" > corpus.txt',
)


class TheDecisionIsMadeOnTheParsedCommand(unittest.TestCase):
    """T-407. GUARD-MENTION-C, reproduced five times, closed by parsing.

    A substring scan cannot tell a mention from a call. The guard blocked an
    `attest.py sign --body` payload, this defect's own bug report, a handoff note listing
    the methods an AST test FORBIDS a module from calling, and the very corpus written to
    repair it. Three of the five were audit trails this harness wants written.

    THE MATRIX HAS BOTH ARMS AND BOTH COUNTS. Only the second arm is the repair; without
    the first it would be indistinguishable from deleting the guard.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        (self.workspace / ".harness" / "logs").mkdir(parents=True)

    def test_arm_a_every_destructive_form_the_regex_guard_blocked_is_still_blocked(self):
        for command in STILL_BLOCKED:
            with self.subTest(command=command):
                self.assertEqual(run_guard(self.workspace, command).returncode, 2, command)

    def test_arm_a_counts_raw_and_distinct(self):
        """TELEMETRY-PROVENANCE-A. A corpus counted once can hide duplicates, and a
        duplicate inflates coverage without adding any."""
        self.assertEqual((len(STILL_BLOCKED), len(set(STILL_BLOCKED))), (56, 56))
        self.assertEqual((len(OPENED_BY_PARSING), len(set(OPENED_BY_PARSING))), (8, 8))

    def test_arm_a_parsing_did_not_open_a_heredoc_into_an_interpreter(self):
        """A heredoc body is data only until an interpreter is on the receiving end.
        `cat > notes.md <<EOF` feeds prose to a file; `bash <<EOF` feeds a program to a
        program. Stripping the body unconditionally would have opened the exact hole this
        guard exists to close."""
        for command in OPENED_BY_PARSING:
            with self.subTest(command=command):
                self.assertEqual(run_guard(self.workspace, command).returncode, 2, command)

    def test_arm_b_prose_describing_a_removal_is_no_longer_blocked(self):
        for command in PROSE_THAT_MUST_PASS:
            with self.subTest(command=command):
                result = run_guard(self.workspace, command)
                self.assertEqual(result.returncode, 0, (command, result.stderr))

    def test_arm_b_counts_raw_and_distinct(self):
        self.assertEqual((len(PROSE_THAT_MUST_PASS), len(set(PROSE_THAT_MUST_PASS))), (5, 5))

    def test_the_lapse_is_named_rather_than_left_to_be_discovered(self):
        """NO SILENT WEAKENING. Two forms the flat scan blocked are now allowed, both of
        them the same shape as the false positives, and neither can be told apart from
        prose without knowing the callee's convention. They are asserted here so the lapse
        is a recorded decision instead of a surprise, and so a future tightening has a
        place to land."""
        for command in (
            'somerunner "rm -rf /"',        # quoted argument to an unknown executable
            'echo "rm -rf project" | sh',   # a command arriving through a pipe, not argv
        ):
            with self.subTest(command=command):
                self.assertEqual(run_guard(self.workspace, command).returncode, 0, command)
        doc = _guard_module().__doc__ or ""
        self.assertIn("WHAT THIS GIVES UP", doc)

    def test_an_unparseable_command_falls_back_to_the_flat_scan(self):
        """Fail closed. An unbalanced quote is not a safe command, and the fallback is the
        strictest behaviour available rather than the most permissive."""
        self.assertEqual(run_guard(self.workspace, 'rm -rf "unterminated').returncode, 2)

    def test_the_module_decides_on_tokens_and_not_on_the_raw_string(self):
        """Parsed, not scanned -- checked by parsing this module rather than grepping it,
        which is the same defect one level up (GUARD-MENTION-C, seventh occurrence)."""
        import ast
        tree = ast.parse(GUARD.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "inspect_command")
        calls = {n.func.attr for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertNotIn("search", calls,
                         "inspect_command runs a regex over text; it must read tokens")
        self.assertNotIn("match", calls)


def _guard_module():
    spec = importlib.util.spec_from_file_location("prevent_data_loss", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The escape a verifier found in the first version of the parsed guard, swept in every form
# it takes. POSIX short flags bundle, so `-lc` is `-l` and `-c` together and hands the next
# token to the shell as code -- and the first version asked whether a token EQUALLED `-c`.
BUNDLED_CODE_FLAGS = (
    'bash -lc "rm -rf /tmp/foo"',
    'bash -cl "rm -rf /tmp/foo"',
    'sh -lc "rm -rf /tmp/foo"',
    'zsh -ic "rm -rf /tmp/foo"',
    'dash -xc "rm -rf /tmp/foo"',
    'ksh -lc "rm -rf /tmp/foo"',
    'bash -ilc "rm -rf /tmp/foo"',
    'bash -lc "git clean -xfd"',
    'sudo bash -lc "rm -rf /tmp/foo"',
    'env bash -lc "rm -rf /tmp/foo"',
    'nohup sh -lc "rm -rf /tmp/foo"',
    'nice bash -lc "rm -rf /tmp/foo"',
    'xargs bash -lc "rm -rf /tmp/foo"',
    'find . -exec bash -lc "rm -rf /tmp/foo" \\;',
    'python3 -Ic "import shutil; shutil.rmtree(\'x\')"',
    'node -pe "require(\'fs\').rmSync(\'x\')"',
)


class BundledShortFlagsAreCodeFlags(unittest.TestCase):
    """The escape past the first version of the parsed guard, found by a verifier.

    `bash -lc "rm -rf ..."` walked straight through: the check asked whether a token EQUALLED
    `-c`, and `-lc` does not. Every bundling and every wrapper combination of it was allowed,
    silently, past a guard whose whole claim was that nothing previously blocked had opened.
    A single-dash token is now a code flag when it CONTAINS one of the executable's own
    single-letter code flags.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        (self.workspace / ".harness" / "logs").mkdir(parents=True)

    def test_every_bundled_form_is_blocked(self):
        for command in BUNDLED_CODE_FLAGS:
            with self.subTest(command=command):
                self.assertEqual(run_guard(self.workspace, command).returncode, 2, command)

    def test_counts_raw_and_distinct(self):
        self.assertEqual((len(BUNDLED_CODE_FLAGS), len(set(BUNDLED_CODE_FLAGS))), (16, 16))

    def test_the_unbundled_controls_were_never_the_problem(self):
        """These always worked. They isolate the defect to the bundled spelling, so a future
        change that breaks the ordinary form fails here instead of hiding behind the fix."""
        for command in ('bash --login -c "rm -rf /tmp/foo"', 'bash -l -c "rm -rf /tmp/foo"'):
            with self.subTest(command=command):
                self.assertEqual(run_guard(self.workspace, command).returncode, 2, command)

    def test_a_bundled_flag_carrying_a_harmless_payload_still_passes(self):
        """NEGATIVE CONTROL. Without it the fix could be "block every bundled flag", which
        would be a guard that stopped parsing and started refusing."""
        for command in ('bash -lc "echo hola"', 'bash -lc "ls -la"'):
            with self.subTest(command=command):
                result = run_guard(self.workspace, command)
                self.assertEqual(result.returncode, 0, (command, result.stderr))

    def test_a_flag_after_the_script_name_belongs_to_the_script(self):
        """`python3 tool.py -c "<prose>"` passes -c to tool.py, not to python. Reading that
        payload as source is the exact false positive this repair exists to remove, and it is
        the shape of the `attest.py sign --body` reproduction."""
        result = run_guard(self.workspace, 'python3 tool.py -c "rm -rf project"')
        self.assertEqual(result.returncode, 0, result.stderr)


class SafeDeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        (self.workspace / ".harness").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_safe(self, *args):
        return subprocess.run(
            [sys.executable, str(SAFE_DELETE), "--root", str(self.workspace), *args],
            text=True,
            capture_output=True,
        )

    def test_quarantine_list_and_restore_preserve_bytes(self):
        source = self.workspace / "project" / "nested" / "data.bin"
        source.parent.mkdir(parents=True)
        content = bytes(range(256))
        source.write_bytes(content)

        quarantined = self.run_safe("quarantine", "project", "--reason", "test cleanup")
        self.assertEqual(quarantined.returncode, 0, quarantined.stderr)
        quarantine_manifest = json.loads(quarantined.stdout)
        entry_id = quarantine_manifest["id"]
        self.assertEqual(quarantine_manifest["reason"], "test cleanup")
        self.assertTrue(quarantine_manifest["agent"])
        self.assertFalse((self.workspace / "project").exists())
        stored = self.workspace / ".harness" / "trash" / entry_id / "payload" / "project" / "nested" / "data.bin"
        self.assertEqual(stored.read_bytes(), content)

        listed = self.run_safe("list")
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(json.loads(listed.stdout)[0]["status"], "quarantined")

        restored = self.run_safe("restore", entry_id)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(source.read_bytes(), content)
        self.assertEqual(json.loads(restored.stdout)["status"], "restored")
        events = [
            json.loads(line)
            for line in (self.workspace / ".harness" / "logs" / "events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            [event["event"] for event in events],
            ["safe_delete_quarantined", "safe_delete_restored"],
        )

    def test_restore_refuses_overwrite_without_losing_either_copy(self):
        source = self.workspace / "notes.txt"
        source.write_text("original")
        result = self.run_safe("quarantine", "notes.txt")
        entry_id = json.loads(result.stdout)["id"]
        source.write_text("new user edit")

        restored = self.run_safe("restore", entry_id)
        self.assertEqual(restored.returncode, 2)
        self.assertEqual(source.read_text(), "new user edit")
        stored = self.workspace / ".harness" / "trash" / entry_id / "payload" / "notes.txt"
        self.assertEqual(stored.read_text(), "original")

    def test_restore_rejects_tampered_stored_paths_before_moving_any_file(self):
        valuable = self.workspace / "valuable.txt"
        valuable.write_text("must stay here")

        for entry_id, stored_path, add_symlink in (
            ("traversal", "../../../valuable.txt", False),
            ("symlink", "payload/escape", True),
        ):
            with self.subTest(stored_path=stored_path):
                entry = self.workspace / ".harness" / "trash" / entry_id
                payload = entry / "payload"
                payload.mkdir(parents=True)
                if add_symlink:
                    (payload / "escape").symlink_to(valuable)
                manifest = {
                    "id": entry_id,
                    "status": "quarantined",
                    "items": [{"original": "stolen.txt", "stored": stored_path}],
                }
                (entry / "manifest.json").write_text(json.dumps(manifest))

                restored = self.run_safe("restore", entry_id)
                self.assertEqual(restored.returncode, 2, restored.stderr)
                self.assertEqual(valuable.read_text(), "must stay here")
                self.assertFalse((self.workspace / "stolen.txt").exists())

    def test_restore_rejects_dot_parent_and_symlink_entry_ids(self):
        for entry_id in (".", ".."):
            with self.subTest(entry_id=entry_id):
                restored = self.run_safe("restore", entry_id)
                self.assertEqual(restored.returncode, 2)

        real_entry = self.workspace / ".harness" / "trash" / "real"
        (real_entry / "payload").mkdir(parents=True)
        (real_entry / "manifest.json").write_text(
            json.dumps({"id": "alias", "status": "quarantined", "items": []})
        )
        alias = real_entry.parent / "alias"
        alias.symlink_to(real_entry, target_is_directory=True)
        restored = self.run_safe("restore", "alias")
        self.assertEqual(restored.returncode, 2)

    def test_refuses_root_outside_and_control_plane(self):
        outside = Path(self.temp.name).parent / (Path(self.temp.name).name + "-outside")
        outside.write_text("outside")
        try:
            protected = self.workspace / ".git"
            protected.mkdir()
            for target in (str(self.workspace), str(outside), ".git"):
                with self.subTest(target=target):
                    result = self.run_safe("quarantine", target)
                    self.assertEqual(result.returncode, 2)
            self.assertTrue(self.workspace.exists())
            self.assertEqual(outside.read_text(), "outside")
            self.assertTrue(protected.exists())
        finally:
            outside.unlink(missing_ok=True)

    def test_cli_exposes_no_purge_command(self):
        result = self.run_safe("purge")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("purge", self.run_safe("--help").stdout.lower())

    def test_refuses_control_plane_case_insensitively(self):
        # CONTROL_PLANE lists the lowercase spelling "claude.md", but the real
        # repo file is CLAUDE.md. Membership must be case-insensitive so the
        # real, differently-cased file is still protected.
        (self.workspace / "CLAUDE.md").write_text("do not quarantine me")
        result = self.run_safe("quarantine", "CLAUDE.md")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("control-plane path is protected", result.stderr)
        self.assertTrue((self.workspace / "CLAUDE.md").exists())


class HookConfigurationTests(unittest.TestCase):
    def test_codex_and_plugin_hooks_enable_guard(self):
        project = json.loads((ROOT / ".codex" / "hooks.json").read_text())
        plugin = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        for config in (project, plugin):
            entries = config["hooks"]["PreToolUse"]
            self.assertTrue(any("prevent_data_loss.py" in hook["command"] for entry in entries for hook in entry["hooks"]))
        project_command = project["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        plugin_command = plugin["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("git rev-parse --show-toplevel", project_command)
        self.assertIn("${PLUGIN_ROOT}", plugin_command)

    def test_claude_settings_wire_guard(self):
        # Operator opt-in 2026-07-11: direct Claude Code sessions in this repo
        # must run the guard too, not only Codex/plugin installs. The command
        # uses $CLAUDE_PROJECT_DIR so the block stays portable to adopter repos.
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        bash_entries = [e for e in settings["hooks"]["PreToolUse"] if e.get("matcher") == "Bash"]
        self.assertTrue(bash_entries)
        commands = [h["command"] for e in bash_entries for h in e["hooks"]]
        guard_commands = [c for c in commands if "prevent_data_loss.py" in c]
        self.assertTrue(guard_commands)
        self.assertTrue(all("$CLAUDE_PROJECT_DIR" in c for c in guard_commands))

    def test_plugin_manifest_references_hooks_file(self):
        # Without a "hooks" key in plugin.json, hooks/hooks.json never loads
        # when this repo is installed as a Codex plugin (the guard would be
        # dead weight, contradicting DATA_LOSS_SAFETY.md).
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest.get("hooks"), "./hooks/hooks.json")
        hooks_path = ROOT / "hooks" / "hooks.json"
        self.assertTrue(hooks_path.exists())


if __name__ == "__main__":
    unittest.main()
