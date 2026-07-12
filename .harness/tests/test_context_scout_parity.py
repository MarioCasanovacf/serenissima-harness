import pathlib
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 remains supported by the harness CLIs.
    tomllib = None


ROOT = pathlib.Path(__file__).resolve().parents[2]


class ContextScoutParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claude = (ROOT / ".claude/agents/context-scout.md").read_text(encoding="utf-8")
        cls.gemini = (ROOT / ".gemini/agents/context-scout.md").read_text(encoding="utf-8")
        if tomllib is not None:
            cls.codex_data = tomllib.loads(
                (ROOT / ".codex/agents/context_scout.toml").read_text(encoding="utf-8")
            )
            cls.codex = cls.codex_data["developer_instructions"]

    @unittest.skipIf(tomllib is None, "TOML parsing requires Python 3.11+")
    def test_codex_profile_is_bounded_to_brief_writes(self):
        self.assertEqual("context_scout", self.codex_data["name"])
        self.assertEqual("workspace-write", self.codex_data["sandbox_mode"])
        self.assertIn("write only that brief", self.codex)
        self.assertIn("Never edit source files", self.codex)

    def test_gemini_profile_is_mechanically_bounded(self):
        self.assertIn("max_turns: 18", self.gemini)
        self.assertIn("timeout_mins: 12", self.gemini)
        self.assertNotIn("  - replace\n", self.gemini)
        self.assertIn("write only that brief", self.gemini)

    @unittest.skipIf(tomllib is None, "TOML parsing requires Python 3.11+")
    def test_all_three_surfaces_share_the_mandate_and_hard_limits(self):
        surfaces = {
            "claude": self.claude,
            "codex": self.codex,
            "gemini": self.gemini,
        }
        required_concepts = (
            "brief",
            "explicit",
            "assum",
            "clarifying questions",
            "file:line",
            "human",
            "never edit source",
            "never design",
            "guess",
        )
        for engine, text in surfaces.items():
            lowered = text.lower()
            for concept in required_concepts:
                self.assertIn(concept.lower(), lowered, f"{engine}: {concept}")
            self.assertRegex(lowered, r"(?:no|never)[^\n]*llm", f"{engine}: LLM ban")
            self.assertRegex(lowered, r"(?:no|never)[^\n]*web", f"{engine}: web ban")

    def test_agent_directory_declares_three_engine_parity(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("Codex/Gemini ports pending", agents)
        self.assertIn("mirrors all six harness mandates", agents)
        self.assertIn("Six bounded, tool-isolated project agents", agents)


if __name__ == "__main__":
    unittest.main()
