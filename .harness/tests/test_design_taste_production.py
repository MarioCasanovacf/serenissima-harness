import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "design-taste-production"
SKILL = ROOT / ".agents" / "skills" / SKILL_NAME
MIRRORS = (
    ROOT / ".claude" / "skills" / SKILL_NAME,
    ROOT / "skills" / SKILL_NAME,
)
REFERENCE_NAMES = {
    "brief-and-direction.md",
    "data-visualization.md",
    "interface-quality.md",
    "marketing-surfaces.md",
    "product-and-transaction.md",
    "redesign-preservation.md",
    "reference-to-code.md",
    "image-concepts.md",
    "style-lenses.md",
    "production-preflight.md",
    "upstream-provenance.md",
    "mario-activation.md",
    "mario-structure-and-voice.md",
    "mario-data-semantics.md",
    "mario-surface-translation.md",
    "mario-executive-memo.md",
    "mario-calibration.md",
}
EXPECTED_FILES = {
    "SKILL.md",
    "LICENSE.upstream",
    *(f"references/{name}" for name in REFERENCE_NAMES),
}
UPSTREAM_URL = "https://github.com/Leonxlnx/taste-skill"
UPSTREAM_COMMIT = "b17742737e796305d829b3ad39eda3add0d79060"
UPSTREAM_LICENSE = """MIT License

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


def split_frontmatter(text: str):
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    metadata = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise AssertionError(f"invalid frontmatter YAML line: {line!r}")
        metadata[key.strip()] = value.strip()
    return metadata, text[match.end() :]


def normalized(path: Path):
    return " ".join(path.read_text(encoding="utf-8").split())


def tree_digest(root: Path):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


class DesignTasteProductionTests(unittest.TestCase):
    def test_skill_structure_has_only_intentional_files(self):
        actual = {
            path.relative_to(SKILL).as_posix()
            for path in SKILL.rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual, EXPECTED_FILES)
        self.assertFalse((SKILL / "scripts").exists())
        self.assertFalse((SKILL / "assets").exists())

    def test_frontmatter_is_valid_yaml_with_exact_keys(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        metadata, body = split_frontmatter(text)
        self.assertEqual(set(metadata), {"name", "description"})
        self.assertEqual(metadata["name"], SKILL_NAME)
        self.assertIsInstance(metadata["description"], str)
        self.assertIn("production-ready web interfaces", metadata["description"])
        self.assertIn("mobile image concepts", metadata["description"])
        self.assertIn("# Design Taste Production", body)
        self.assertLess(len(text.splitlines()), 250)

    def test_universal_mirrors_are_byte_identical(self):
        expected = tree_digest(SKILL)
        self.assertTrue(expected)
        for mirror in MIRRORS:
            with self.subTest(mirror=mirror):
                self.assertEqual(tree_digest(mirror), expected)

    def test_core_has_no_vendor_or_runtime_dependency(self):
        corpus = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SKILL.rglob("*"))
            if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json"}
        ).casefold()
        for vendor in (
            "openai",
            "anthropic",
            "chatgpt",
            "claude",
            "codex",
            "gemini",
            "agents/openai.yaml",
        ):
            with self.subTest(vendor=vendor):
                self.assertNotIn(vendor, corpus)
        skill = normalized(SKILL / "SKILL.md")
        for phrase in (
            "independent of the model, agent runtime, command-line tool, vendor",
            "Runtime-specific discovery",
            "must not change the skill's semantics",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

    def test_router_links_every_reference_directly_and_only_once_per_target(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        linked = set(re.findall(r"\]\(references/([a-z0-9-]+\.md)\)", text))
        self.assertEqual(linked, REFERENCE_NAMES)
        self.assertEqual(
            {path.name for path in (SKILL / "references").glob("*.md")},
            REFERENCE_NAMES,
        )
        self.assertFalse(
            [path for path in (SKILL / "references").rglob("*") if path.is_dir()]
        )

    def test_mode_lock_covers_all_supported_work(self):
        skill = normalized(SKILL / "SKILL.md")
        for phrase in (
            "Lock the operating mode",
            "Marketing / conversion",
            "Product / task",
            "Transactional flow",
            "Redesign: preserve",
            "Redesign: overhaul",
            "Reference to code",
            "Visual review",
            "Image concept",
            "do not silently switch modes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

    def test_core_is_stack_neutral_and_preserves_product_contracts(self):
        skill = normalized(SKILL / "SKILL.md")
        for phrase in (
            "existing framework, package manager",
            "design system",
            "data and API contracts",
            "state semantics",
            "routes, forms, analytics",
            "consent and legal behavior",
            "accessibility, SEO",
            "Overhaul mode is not permission to break them",
            "Reuse installed dependencies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

    def test_dashboards_and_multistep_transactions_are_first_class(self):
        skill = normalized(SKILL / "SKILL.md")
        product = normalized(
            SKILL / "references" / "product-and-transaction.md"
        )
        self.assertIn("including dashboards", skill)
        self.assertIn("multi-step flows", skill)
        for phrase in (
            "overview, exceptions, detail, and actions",
            "units, time range, freshness",
            "step sequence, branching, validation, side effects, persistence",
            "idempotency",
            "destructive actions",
            "resumed-session states",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, product)

    def test_motion_and_image_tools_are_conditional(self):
        skill = normalized(SKILL / "SKILL.md")
        images = normalized(SKILL / "references" / "image-concepts.md")
        self.assertIn(
            "Use image generation, image search, or browsing only when available, "
            "authorized, and necessary",
            skill,
        )
        self.assertIn("Motion libraries are conditional", skill)
        self.assertIn("Image tooling is optional", images)
        self.assertIn("clearly labeled placeholder", images)

    def test_mario_profile_is_explicit_conditional_and_semantic(self):
        skill = normalized(SKILL / "SKILL.md")
        activation = normalized(SKILL / "references" / "mario-activation.md")
        semantics = normalized(SKILL / "references" / "mario-data-semantics.md")
        self.assertIn("exact `personal:mario` flag", skill)
        self.assertIn("remain brand-neutral", skill)
        self.assertIn("light paper canvas is not a default", skill)
        self.assertIn("Do not infer activation", activation)
        for phrase in (
            "Positive / success | Forest | `#2E4A3F`",
            "Warning | Ochre | `#A87333`",
            "Negative / critical | Oxblood | `#6E1F1F`",
            "Neutral | Warm grey | `#6B655C`",
            "Structure / reference / total | Ink | `#1A1814`",
            "Prevent CTA/status collision",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, semantics)

    def test_data_visualization_uses_geometry_and_semantic_color(self):
        skill = normalized(SKILL / "SKILL.md")
        data = normalized(SKILL / "references" / "data-visualization.md")
        semantics = normalized(SKILL / "references" / "mario-data-semantics.md")
        surface = normalized(SKILL / "references" / "mario-surface-translation.md")
        self.assertIn("Data visualization", skill)
        for phrase in (
            "A graph is evidence, not texture",
            "Anchor every numeric label to the mark or segment it describes",
            "Use at most one grey data encoding",
            "font-variant-numeric: tabular-nums lining-nums",
            "do not manually nudge individual digits",
            "Keep each ISO date token unbroken",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, data)
        for phrase in (
            "Use semantic chart recipes",
            "never accompany it with a lighter, darker, or translucent grey data series",
            "Never place unequal segment values in equal-width label columns",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, semantics)
        self.assertIn("Align every displayed number to a common grid or baseline", surface)

    def test_mobile_multiframe_image_contract_is_explicit(self):
        images = normalized(SKILL / "references" / "image-concepts.md")
        for phrase in (
            "platform conventions, safe areas and system regions",
            "navigation model, keyboard behavior, typography, spacing, radii, and icon",
            "Map the logical flow",
            "design bible across every screen",
            "raw screens or device mockups",
            "never force a phone frame",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, images)

    def test_deliverable_completeness_and_placeholder_contract(self):
        skill = normalized(SKILL / "SKILL.md")
        preflight = normalized(
            SKILL / "references" / "production-preflight.md"
        )
        self.assertIn("Enumerate every requested deliverable", skill)
        self.assertIn("cross-check every requested deliverable", skill)
        self.assertIn("truly missing external assets or dependencies", skill)
        self.assertIn("dimensions, role, and replacement next step", preflight)

    def test_no_brittle_upstream_recipe_is_mandated(self):
        corpus = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SKILL.rglob("*.md"))
        )
        forbidden = (
            "must use React",
            "must use Tailwind",
            "must use GSAP",
            "always use dark mode",
            "never use an em dash",
            "never use an en dash",
            "Math.random",
            "one image in every section",
            "one image per section is required",
        )
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.casefold(), corpus.casefold())

    def test_upstream_provenance_and_full_license_are_pinned(self):
        provenance = (
            SKILL / "references" / "upstream-provenance.md"
        ).read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_URL, provenance)
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn("License: MIT", provenance)
        self.assertEqual(
            (SKILL / "LICENSE.upstream").read_text(encoding="utf-8"),
            UPSTREAM_LICENSE,
        )


if __name__ == "__main__":
    unittest.main()
