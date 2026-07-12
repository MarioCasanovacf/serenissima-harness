import pathlib
import re
import json
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def frontmatter(path: pathlib.Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    raw, _body = text[4:].split("\n---\n", 1)
    result: dict[str, object] = {}
    current_list: list[str] | None = None
    for line in raw.splitlines():
        if line.startswith("  - ") and current_list is not None:
            current_list.append(line[4:].strip())
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if not value:
            current_list = []
            result[key] = current_list
        elif value.isdigit():
            current_list = None
            result[key] = int(value)
        else:
            current_list = None
            result[key] = value
    return result


def command_toml(path: pathlib.Path) -> dict[str, str]:
    """Parse the deliberately small command schema on Python versions before 3.11."""
    text = path.read_text(encoding="utf-8")
    description = re.search(r'^description\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    prompt = re.search(r'^prompt\s*=\s*"""(.*?)"""\s*$', text, re.MULTILINE | re.DOTALL)
    if not description or not prompt:
        raise AssertionError(f"invalid command TOML shape: {path}")
    return {"description": description.group(1), "prompt": prompt.group(1)}


class GeminiIntegrationTests(unittest.TestCase):
    def test_context_configuration_loads_existing_shared_contracts(self):
        data = json.loads((ROOT / ".gemini/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(
            ["gemini.md", "AGENTS.md", "ORCHESTRATION.md", "GEMINI_ADAPTER.md"],
            data["context"]["fileName"],
        )
        for name in data["context"]["fileName"]:
            self.assertTrue((ROOT / name).is_file(), name)
        adapter = (ROOT / "GEMINI_ADAPTER.md").read_text(encoding="utf-8")
        self.assertRegex(adapter, r"(?i)Gemini CLI or Antigravity may act as the\s+coordinator")
        self.assertRegex(adapter, r"(?i)external side effect\s+are disabled unless the human operator explicitly opts in")

    def test_six_native_agents_are_bounded_and_tool_isolated(self):
        expected = {
            "orchestration-planner",
            "substrate-worker",
            "harness-verifier",
            "evolution-analyst",
            "research-librarian",
            "context-scout",
        }
        paths = list((ROOT / ".gemini/agents").glob("*.md"))
        parsed = {frontmatter(path)["name"]: frontmatter(path) for path in paths}
        self.assertEqual(expected, set(parsed))
        for name, data in parsed.items():
            self.assertEqual("local", data["kind"], name)
            self.assertGreater(data["max_turns"], 0, name)
            self.assertLessEqual(data["max_turns"], 30, name)
            self.assertGreater(data["timeout_mins"], 0, name)
            self.assertLessEqual(data["timeout_mins"], 20, name)
            self.assertNotIn("*", data["tools"], name)

        for name in ("harness-verifier", "research-librarian"):
            self.assertNotIn("write_file", parsed[name]["tools"])
            self.assertNotIn("replace", parsed[name]["tools"])
        self.assertNotIn("run_shell_command", parsed["research-librarian"]["tools"])
        self.assertNotIn("replace", parsed["context-scout"]["tools"])

    def test_namespaced_commands_are_valid_toml_and_have_fallbacks(self):
        command_dir = ROOT / ".gemini/commands/harness"
        expected = {"status", "claim", "orchestrate", "verify", "audit", "research"}
        self.assertEqual(expected, {path.stem for path in command_dir.glob("*.toml")})
        for path in command_dir.glob("*.toml"):
            data = command_toml(path)
            self.assertIsInstance(data.get("description"), str, path.name)
            self.assertIsInstance(data.get("prompt"), str, path.name)
            self.assertTrue(data["prompt"].strip(), path.name)
        for name in ("claim", "orchestrate", "audit", "research"):
            text = (command_dir / f"{name}.toml").read_text(encoding="utf-8")
            self.assertRegex(text, r"(?i)fallback")

    def test_antigravity_workflows_have_frontmatter_and_independent_review(self):
        workflow_dir = ROOT / ".agents/workflows"
        expected = {
            "harness-status",
            "plan-and-fill-board",
            "work-frontier",
            "review-queue",
            "run-harness-cycle",
            "harness-audit",
            "research-corpus",
        }
        self.assertTrue(expected.issubset({path.stem for path in workflow_dir.glob("*.md")}))
        for name in expected:
            data = frontmatter(workflow_dir / f"{name}.md")
            self.assertTrue(data.get("description"), name)
        review = (workflow_dir / "review-queue.md").read_text(encoding="utf-8")
        cycle = (workflow_dir / "run-harness-cycle.md").read_text(encoding="utf-8")
        self.assertRegex(review, r"(?i)(fresh|did not produce)")
        self.assertRegex(cycle, r"(?i)(fresh|different from)")

    def test_every_role_has_a_non_preview_entry_point(self):
        command_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".gemini/commands/harness").glob("*.toml")
        )
        workflow_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".agents/workflows").glob("*.md")
        )
        for concept in ("planner", "worker", "verifier", "evolution", "research"):
            self.assertIn(concept, (command_text + workflow_text).lower())

    def test_runtime_instructions_use_portable_lowercase_constitution_name(self):
        paths = list((ROOT / ".gemini/agents").glob("*.md"))
        paths += list((ROOT / ".gemini/commands/harness").glob("*.toml"))
        paths += list((ROOT / ".agents/workflows").glob("*.md"))
        for path in paths:
            self.assertNotIn("`GEMINI.md`", path.read_text(encoding="utf-8"), path)


if __name__ == "__main__":
    unittest.main()
