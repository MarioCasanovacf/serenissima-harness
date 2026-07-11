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
