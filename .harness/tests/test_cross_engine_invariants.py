import pathlib
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 remains supported by the harness CLIs.
    tomllib = None


ROOT = pathlib.Path(__file__).resolve().parents[2]


# One semantic contract, checked against engine-native wording. These patterns
# deliberately avoid byte identity: adapters may explain the same invariant in
# the vocabulary their host understands.
ROLE_CONTRACTS = {
    "worker": {
        "paths": {
            "claude": ".claude/agents/substrate-worker.md",
            "codex": ".codex/agents/substrate_worker.toml",
            "gemini": ".gemini/agents/substrate-worker.md",
        },
        "invariants": {
            "claim from guarded blackboard": (
                r"blackboard\.py\s+(?:next|claim)",
                r"\bclaim\b",
            ),
            "lock before every write": (
                r"lock[^\n]{0,80}(?:every|for every)[^\n]{0,80}(?:file|target)",
                r"(?:before (?:editing|writing)|before every write)",
            ),
            "handoff instead of self-approval": (
                r"handoff[\s\S]{0,80}(?:verifier|review)",
                r"never (?:sets?|set|marks?)[\s\S]{0,80}(?:own|itself)[\s\S]{0,40}done",
            ),
            "blackboard mutations use sanctioned CLI": (
                r"(?:hand-edit[^\n]{0,80}(?:json|blackboard)|(?:blackboard\.json|state\.json)[^\n]{0,40}by hand)",
                r"blackboard\.py",
            ),
        },
    },
    "verifier": {
        "paths": {
            "claude": ".claude/agents/harness-verifier.md",
            "codex": ".codex/agents/harness_verifier.toml",
            "gemini": ".gemini/agents/harness-verifier.md",
        },
        "invariants": {
            "producer differs from approver": (
                r"(?:producer\s*(?:!=|≠)[^\n]*approver|identity[^\n]{0,100}differs?[^\n]{0,60}producer|never approve[^\n]{0,100}same identity)",
            ),
            "verifier never becomes a writer": (
                r"never (?:edit|repair)[^\n]{0,80}(?:source|code|implementation|artifact)",
            ),
            "verdict mutates state only through blackboard CLI": (
                r"(?:verdict|task)[^\n]{0,160}(?:only through|through|with)[^\n]{0,80}blackboard\.py|blackboard\.py[^\n]{0,100}(?:verdict|status done)",
                r"(?:never hand-edit[^\n]{0,80}(?:json|state)|sanctioned cli|only through `?blackboard\.py)",
            ),
        },
    },
}


def role_text(path: pathlib.Path) -> str:
    """Return prose instructions, excluding Codex TOML metadata when possible."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml" and tomllib is not None:
        return tomllib.loads(text)["developer_instructions"]
    return text


class CrossEngineInvariantTests(unittest.TestCase):
    def test_role_contracts_preserve_shared_semantics(self):
        for role, contract in ROLE_CONTRACTS.items():
            for engine, relative_path in contract["paths"].items():
                text = role_text(ROOT / relative_path)
                for invariant, patterns in contract["invariants"].items():
                    with self.subTest(role=role, engine=engine, invariant=invariant):
                        for pattern in patterns:
                            self.assertRegex(text, re.compile(pattern, re.IGNORECASE))

    def test_contract_covers_all_three_engines_for_both_mutating_roles(self):
        for role, contract in ROLE_CONTRACTS.items():
            with self.subTest(role=role):
                self.assertEqual({"claude", "codex", "gemini"}, set(contract["paths"]))


if __name__ == "__main__":
    unittest.main()
