import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "design-taste-frontend"
CANONICAL = ROOT / ".agents" / "skills" / SKILL_NAME
MIRRORS = (
    ROOT / ".claude" / "skills" / SKILL_NAME,
    ROOT / "skills" / SKILL_NAME,
)
REFERENCE_FILES = {
    "taste-rules.md",
    "react-next-tailwind.md",
    "motion-patterns.md",
    "redesign.md",
    "preflight.md",
    "upstream-provenance.md",
}
UPSTREAM_URL = "https://github.com/Leonxlnx/taste-skill"
UPSTREAM_COMMIT = "b17742737e796305d829b3ad39eda3add0d79060"
MIT_TEXT = """MIT License

Copyright (c) 2026 Leonxlnx

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def tree_digest(root: Path):
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def split_frontmatter(text: str):
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise AssertionError("SKILL.md must begin with YAML frontmatter")
    fields = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"invalid frontmatter line: {line!r}")
        fields[key.strip()] = value.strip()
    return fields, text[match.end():]


class UniversalSkillIntegrationTests(unittest.TestCase):
    def test_canonical_skill_has_expected_name_and_small_router(self):
        text = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        fields, body = split_frontmatter(text)
        self.assertEqual(set(fields), {"name", "description"})
        self.assertEqual(fields["name"], SKILL_NAME)
        self.assertTrue(fields["description"])
        self.assertLess(len(text.splitlines()), 500)
        self.assertIn("# Design Taste Frontend", body)

    def test_all_direct_references_exist_at_one_level(self):
        skill_text = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        linked = set(re.findall(r"\]\(references/([a-z0-9-]+\.md)\)", skill_text))
        self.assertEqual(linked, REFERENCE_FILES)
        self.assertEqual(
            {path.name for path in (CANONICAL / "references").glob("*.md")},
            REFERENCE_FILES,
        )
        self.assertFalse(
            [path for path in (CANONICAL / "references").rglob("*") if path.is_dir()]
        )

    def test_three_skill_trees_are_recursively_identical(self):
        expected = tree_digest(CANONICAL)
        self.assertTrue(expected)
        for mirror in MIRRORS:
            with self.subTest(mirror=mirror):
                self.assertEqual(tree_digest(mirror), expected)

    def test_portable_core_preserves_existing_project(self):
        text = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        required = (
            "preserve its framework, package manager",
            "design tokens",
            "information architecture",
            "analytics hooks",
            "accessibility behavior",
            "Do not assume React, Next.js,",
            "Do not change framework or package manager",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_framework_motion_and_tools_are_conditional(self):
        skill = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        normalized_skill = " ".join(skill.split())
        framework = (CANONICAL / "references" / "react-next-tailwind.md").read_text(
            encoding="utf-8"
        )
        motion = (CANONICAL / "references" / "motion-patterns.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("only when the inspected project", normalized_skill)
        self.assertIn("Motion is optional", motion)
        self.assertIn("This branch is not the portable default", framework)
        self.assertIn(
            "Authorized, available image-generation or web tooling", normalized_skill
        )
        self.assertIn("Explicitly labeled placeholder slots", normalized_skill)
        self.assertIn("Never call an external LLM API", normalized_skill)

    def test_scope_and_full_workflow_are_declared(self):
        text = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for heading in (
            "## Scope",
            "## Core workflow",
            "## Reference routing",
            "## Conditional tools and assets",
            "## Delivery contract",
        ):
            self.assertIn(heading, text)
        for excluded in (
            "dense dashboards",
            "data tables",
            "multi-step product flows",
            "native mobile",
        ):
            self.assertIn(excluded, normalized)
        self.assertIn("public-facing portions", normalized)

    def test_upstream_provenance_and_license_are_complete(self):
        provenance = (
            CANONICAL / "references" / "upstream-provenance.md"
        ).read_text(encoding="utf-8")
        license_text = (CANONICAL / "LICENSE.upstream").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_URL, provenance)
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertEqual(license_text, MIT_TEXT)
        self.assertIn("MIT", provenance)

    def test_capability_indexes_document_current_skill_discovery(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        gemini_adapter = (ROOT / "GEMINI_ADAPTER.md").read_text(encoding="utf-8")

        for text in (agents, readme):
            self.assertIn(SKILL_NAME, text)
            for surface_link in (
                "[.agents/skills/](.agents/skills/)",
                "[.claude/skills/](.claude/skills/)",
                "[skills/](skills/)",
            ):
                self.assertIn(surface_link, text)

        self.assertIn("discovered directly by Codex and Gemini CLI", readme)
        self.assertNotIn("future interoperability surface", readme)
        normalized_adapter = " ".join(gemini_adapter.split())
        self.assertIn("non-normative", normalized_adapter)
        self.assertIn("automatically discovers repo-scoped", normalized_adapter)
        self.assertIn("[.agents/skills/](.agents/skills/)", normalized_adapter)
        self.assertIn("independent of context-file injection", normalized_adapter)
        self.assertIn("shared blackboard lifecycle", normalized_adapter)
        self.assertIn("not a claim", normalized_adapter)
        self.assertIn(
            "https://geminicli.com/docs/cli/using-agent-skills/",
            normalized_adapter,
        )

    def test_agents_index_covers_every_canonical_skill_directory(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        skill_names = {
            path.parent.name
            for path in (ROOT / ".agents" / "skills").glob("*/SKILL.md")
        }
        self.assertTrue(skill_names)
        for name in skill_names:
            with self.subTest(name=name):
                self.assertIn(name, agents)


if __name__ == "__main__":
    unittest.main()
