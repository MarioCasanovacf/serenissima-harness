import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 remains supported by the harness CLIs.
    tomllib = None


ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / ".codex" / "agents"
SKILLS_DIR = ROOT / ".agents" / "skills"


class CodexIntegrationTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, "TOML parsing requires Python 3.11+")
    def test_project_config_bounds_parallelism(self):
        config = tomllib.loads((ROOT / ".codex" / "config.toml").read_text())
        self.assertEqual(config["agents"]["max_threads"], 4)
        self.assertEqual(config["agents"]["max_depth"], 1)

    @unittest.skipIf(tomllib is None, "TOML parsing requires Python 3.11+")
    def test_six_native_agent_profiles_are_valid(self):
        expected = {
            "orchestration_planner",
            "substrate_worker",
            "harness_verifier",
            "evolution_analyst",
            "research_librarian",
            "context_scout",
        }
        profiles = {}
        for path in AGENTS_DIR.glob("*.toml"):
            parsed = tomllib.loads(path.read_text())
            profiles[parsed["name"]] = parsed
            self.assertTrue(parsed["description"].strip(), path)
            self.assertTrue(parsed["developer_instructions"].strip(), path)
        self.assertEqual(set(profiles), expected)
        self.assertEqual(profiles["research_librarian"]["sandbox_mode"], "read-only")
        self.assertIn("Never set your own task to done", profiles["substrate_worker"]["developer_instructions"])
        self.assertIn("Never edit source files", profiles["harness_verifier"]["developer_instructions"])

    def test_shared_codex_skills_have_frontmatter_and_contracts(self):
        expected = {"harness-status", "harness-claim-next", "harness-orchestrate"}
        found = {}
        for path in SKILLS_DIR.glob("*/SKILL.md"):
            text = path.read_text()
            if not text.startswith("---\n"):
                continue
            frontmatter = text.split("---", 2)[1]
            name_line = next(line for line in frontmatter.splitlines() if line.startswith("name:"))
            found[name_line.split(":", 1)[1].strip()] = text
        self.assertTrue(expected.issubset(found))
        self.assertIn("all read-only", found["harness-status"])
        self.assertIn("--engine codex", found["harness-claim-next"])
        self.assertIn("native Codex subagents", found["harness-orchestrate"])

    def test_blackboard_accepts_codex_engine(self):
        spec = importlib.util.spec_from_file_location(
            "blackboard", ROOT / ".harness" / "bin" / "blackboard.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT / ".harness" / "bin"))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        self.assertEqual(module.VALID_ENGINES, ["claude", "gemini", "codex", "any"])

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".harness" / "bin" / "blackboard.py"),
                "next",
                "--agent",
                "codex-smoke",
                "--engine",
                "codex",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        if result.returncode == 0:
            self.assertIn("claim it:", result.stdout)
            self.assertIn("--agent codex-smoke", result.stdout)
        else:
            self.assertIn("no claimable task", result.stdout)
            self.assertIn("engine=codex", result.stdout)

    def test_codex_plugin_manifest_and_skill_sync(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "serenissima-harness")
        self.assertEqual(manifest["skills"], "./skills/")

        for name in ("harness-status", "harness-claim-next", "harness-orchestrate"):
            project_skill = SKILLS_DIR / name / "SKILL.md"
            plugin_skill = ROOT / "skills" / name / "SKILL.md"
            self.assertEqual(project_skill.read_text().strip(), plugin_skill.read_text().strip())

        claude_status = ROOT / ".claude" / "skills" / "harness-status" / "SKILL.md"
        project_status = SKILLS_DIR / "harness-status" / "SKILL.md"
        plugin_status = ROOT / "skills" / "harness-status" / "SKILL.md"
        self.assertEqual(claude_status.read_bytes(), project_status.read_bytes())
        self.assertEqual(claude_status.read_bytes(), plugin_status.read_bytes())

    def test_tracked_gemini_adapter_declares_local_execution_surfaces(self):
        adapter = (ROOT / "GEMINI_ADAPTER.md").read_text(encoding="utf-8")
        self.assertIn("Gemini CLI", adapter)
        self.assertIn("Antigravity", adapter)
        self.assertIn("gemini_headless_runner.py", adapter)

if __name__ == "__main__":
    unittest.main()
