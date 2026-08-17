"""Pins the signing command that `warrant.py draft` prints to the operator.

Why this file exists, stated plainly: this one string reached the operator BROKEN THREE
TIMES on 2026-08-17, and each failure cost a round trip and ended in the same message,
`agent refused operation`.

  1. `-f ~/.ssh/harness_root.pub -U` — the agent route. Fails because `ssh-add -c` makes
     the AGENT the party that must display a confirmation, and on macOS SSH_AUTH_SOCK
     points at Apple's launchd-managed agent, which has its own environment and never sees
     an SSH_ASKPASS exported in a shell.
  2. The same command again, after a repair that misdiagnosed the cause as a missing
     askpass program. Supplying an askpass is necessary but not sufficient: it cannot
     reach that agent at all.
  3. `-f ~/.ssh/harness_root` with no -U. This looked right and still failed, because
     `ssh-keygen -Y sign` tries the private key with an EMPTY passphrase first and, when
     that fails, FALLS BACK TO THE AGENT instead of prompting. The passphrase-protected
     key was in the agent under -c, so the fallback landed on the same refusal. The reason
     this was not caught: the verification run used a key with NO passphrase, so the
     fallback path was never exercised.

The fix is `SSH_AUTH_SOCK= ` in front. With no agent to fall back to, ssh-keygen reads
the file and asks for the passphrase on the terminal, which is the human-presence check
the whole custody model rests on. Reproduced in both directions against a
passphrase-protected key loaded under `ssh-add -c`.

These tests are string assertions on purpose. They cannot prove the command signs; only a
key and a human can do that. What they CAN do is stop a future edit from silently deleting
a piece whose absence has already been measured. Every assertion below names the failure
it is standing in front of.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WARRANT = ROOT / ".harness" / "bin" / "warrant.py"

sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import warrant  # noqa: E402


class TheEmittedCommand(unittest.TestCase):
    """Runs `draft` for real in a sandbox root and reads what it printed."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(cls._tmp.name)
        (base / ".harness").mkdir()
        agent = base / "agent"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                        "-f", str(agent), "-C", "agent"], check=True)
        out = subprocess.run(
            [sys.executable, str(WARRANT), "--root", str(base / ".harness"), "draft",
             "--epic", "epic-sign-command-test",
             "--colegiado", "banco=paga por prestamos cobrados",
             "--plaza", "banco/judge=1",
             "--name", "worker-a:banco/judge:{}:Ana".format(agent.with_suffix(".pub"))],
            capture_output=True, text=True, check=True)
        cls.result = json.loads(out.stdout)
        cls.cmd = cls.result["sign_with"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_it_empties_the_agent_socket(self):
        # Failure 3. Without this the command falls back to the agent and is refused.
        self.assertTrue(
            self.cmd.startswith("SSH_AUTH_SOCK= "),
            "the command must begin with an emptied SSH_AUTH_SOCK; got: " + self.cmd)

    def test_the_socket_is_emptied_only_for_this_command(self):
        # A prefixed assignment scopes to the one process. `export SSH_AUTH_SOCK=` or a
        # separate `unset` line would disarm the operator's agent for the whole shell.
        self.assertNotIn("export", self.cmd)
        self.assertNotIn("unset", self.cmd)
        self.assertNotIn(";", self.cmd)
        self.assertNotIn("&&", self.cmd)

    def test_it_points_at_the_private_key(self):
        # Failures 1 and 2 pointed -f at the .pub file.
        self.assertIn("-f ~/.ssh/harness_root ", self.cmd)
        self.assertNotIn("harness_root.pub", self.cmd)

    def test_it_does_not_use_dash_U(self):
        # -U forces the agent route back in, which is the thing that does not work here.
        self.assertNotIn(" -U", self.cmd)

    def test_it_signs_the_payload_that_draft_just_wrote(self):
        self.assertIn(self.result["path"], self.cmd)
        self.assertTrue(pathlib.Path(self.result["path"]).is_file())

    def test_it_uses_the_reserved_namespace(self):
        self.assertIn("-n harness-warrant ", self.cmd)
        self.assertEqual(warrant.NAMESPACE, "harness-warrant")

    def test_the_rationale_travels_with_the_command(self):
        # An operator who is handed a command with a bare `SSH_AUTH_SOCK=` in front will
        # reasonably want to know why, and a future editor needs to know before deleting it.
        why = self.result["WHY_EVERY_PART_OF_THAT_COMMAND"]
        for token in ("SSH_AUTH_SOCK", "falls back", "agent refused operation",
                      "PRIVATE key", "-U"):
            self.assertIn(token, why)

    def test_the_note_promises_a_terminal_prompt_not_a_dialog(self):
        # The dialog is what did not work. Promising one again would be the same defect.
        note = self.result["note"].lower()
        self.assertIn("passphrase", note)
        self.assertIn("terminal", note)
        self.assertNotIn("dialog", note)
        self.assertNotIn("confirm", note)


class TheConstants(unittest.TestCase):
    """The command is assembled from module constants so it exists in exactly one place."""

    def test_the_pieces_are_constants(self):
        self.assertEqual(warrant.SIGN_ENV, "SSH_AUTH_SOCK= ")
        self.assertEqual(warrant.ROOT_KEY, "~/.ssh/harness_root")

    # The two checks below were first written as substring scans over the source. Both
    # failed, and on their own subject: the words `ssh-add`, `SSH_ASKPASS` and
    # `ssh-keygen -Y sign` all appear inside SIGN_RATIONALE, which is the prose that
    # EXPLAINS the command. That is defect GUARD-MENTION-C, already on this project's
    # register: a substring scan cannot tell a mention from a call. So they parse instead.

    @staticmethod
    def tree():
        import ast
        return ast.parse((ROOT / ".harness" / "bin" / "warrant.py").read_text(encoding="utf-8"))

    @staticmethod
    def string_constants(node):
        import ast
        return [n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]

    def test_the_command_is_assembled_in_exactly_one_place(self):
        # Two copies is how a repair fixes one and misses the other. Counted over string
        # constants that are NOT the rationale, so the explanation does not count itself.
        import ast
        tree = self.tree()
        rationale = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
                if targets & {"SIGN_RATIONALE"}:
                    rationale.update(self.string_constants(node))
        hits = [s for s in self.string_constants(tree)
                if "ssh-keygen -Y sign" in s and s not in rationale]
        self.assertEqual(len(hits), 1,
                         "expected one assembled command outside the rationale, got: %r" % hits)

    @classmethod
    def argv_lists(cls):
        """Every literal argv the module hands to a subprocess, as (lineno, [args])."""
        import ast
        out = []
        for node in ast.walk(cls.tree()):
            if not isinstance(node, ast.Call):
                continue
            for a in node.args:
                if isinstance(a, (ast.List, ast.Tuple)):
                    argv = [x.value for x in a.elts
                            if isinstance(x, ast.Constant) and isinstance(x.value, str)]
                    if argv and argv[0].split("/")[-1].startswith("ssh"):
                        out.append((getattr(node, "lineno", "?"), argv))
        return out

    def test_no_call_in_the_module_signs(self):
        # The property that matters most. Asserted structurally so this file cannot be read
        # as permission to make signing convenient. NOT a ban on ssh-keygen: the module
        # legitimately calls `-lf` to read a fingerprint and `-Y verify` to check a
        # signature. Only signing is forbidden, and only the operator can do it.
        signing = [(ln, argv) for ln, argv in self.argv_lists()
                   if "sign" in argv or argv[0].split("/")[-1] in ("ssh-add", "ssh-agent")]
        self.assertEqual(signing, [],
                         "warrant.py must never sign or drive an agent: %r" % signing)

    def test_the_ssh_calls_it_does_make_are_read_only(self):
        allowed = {("-lf",), ("-Y", "verify")}
        for ln, argv in self.argv_lists():
            verb = tuple(argv[1:3]) if argv[1:2] == ["-Y"] else tuple(argv[1:2])
            self.assertIn(verb, allowed,
                          "line %s calls ssh with an unexpected verb %r" % (ln, verb))


class TheDocumentsAgree(unittest.TestCase):
    """The operator reads prose, not this module. A doc that contradicts the tool is how
    a broken command survives a code fix."""

    LIVE = ROOT / ".harness"

    def docs(self):
        for name in ("OPERATOR-ENROLMENT.md", "W-002-BRIEFING.md"):
            p = self.LIVE / name
            if p.is_file():
                yield p, p.read_text(encoding="utf-8")

    def test_no_document_hands_over_a_bare_private_key_sign_command(self):
        # Route A in OPERATOR-ENROLMENT.md legitimately keeps `-f <pubkey> -U` behind a
        # privately started agent. What must never appear is the private-key form WITHOUT
        # the emptied socket, because that is failure 3 verbatim.
        for path, text in self.docs():
            for line in text.splitlines():
                s = line.strip().lstrip("$ ")
                if not s.startswith("ssh-keygen -Y sign"):
                    continue
                if "-U" in s:
                    continue  # the agent route, correct in its own section
                self.fail(
                    "{}: a private-key sign command with no SSH_AUTH_SOCK= prefix, which "
                    "is the exact form that failed on the operator's machine: {}"
                    .format(path.name, s))

    def test_at_least_one_document_carries_the_working_command(self):
        found = any("SSH_AUTH_SOCK= ssh-keygen -Y sign" in text for _, text in self.docs())
        self.assertTrue(found, "no operator-facing document carries the working command")


if __name__ == "__main__":
    unittest.main()
