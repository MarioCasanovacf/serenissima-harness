"""Tests for askpass_macos.sh, the helper that lets `ssh-add -c` actually prompt.

Why this file exists: `OPERATOR-ENROLMENT.md` told the operator to load the root key
with `ssh-add -c` and then sign with `ssh-keygen -Y sign ... -U`. On a stock macOS
that sequence CANNOT SUCCEED. `-c` makes ssh-agent demand confirmation, confirmation
needs an askpass program, macOS ships none, and OpenSSH does not fail open: it
refuses the signature. The operator hit exactly that on 2026-08-17
("agent refused operation"). The enrolment document had been described as tested end
to end; the `-U` branch had not been.

Scope, so this file does not get read as a fix it is not. Supplying the helper is
NECESSARY but not SUFFICIENT: SSH_AUTH_SOCK points at Apple's launchd-managed agent
by default, that agent has its own environment, and it never sees an SSH_ASKPASS
exported in a shell. The helper only reaches an agent the operator starts themselves.
That is Route A of the enrolment document. The default route signs with the private
key and no `-U`, involves no agent, and demands the passphrase on the terminal.

The property that matters most here is FAIL CLOSED. An askpass that returns success
when its dialog breaks would silently authorize every signature the agent is asked
for, which is strictly worse than having no askpass at all. The dialog is stubbed so
these run headless and never touch the operator's screen or key.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".harness" / "bin" / "askpass_macos.sh"


class AskpassCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.stubdir = pathlib.Path(self._tmp.name)

    def stub_osascript(self, body):
        """Replace osascript on PATH so no real dialog is ever displayed."""
        path = self.stubdir / "osascript"
        path.write_text("#!/bin/sh\ncat >/dev/null\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    def run_askpass(self, confirm=True, prompt="test"):
        env = dict(os.environ)
        env["PATH"] = "{}:{}".format(self.stubdir, env.get("PATH", ""))
        if confirm:
            env["SSH_ASKPASS_PROMPT"] = "confirm"
        else:
            env.pop("SSH_ASKPASS_PROMPT", None)
        return subprocess.run(["/bin/sh", str(SCRIPT), prompt], env=env,
                              capture_output=True, text=True, timeout=30)


class ConfirmationMode(AskpassCase):
    """In confirmation mode ssh-agent reads the EXIT STATUS, never stdout."""

    def test_authorising_exits_zero(self):
        self.stub_osascript('echo ALLOW')
        self.assertEqual(self.run_askpass().returncode, 0)

    def test_denying_exits_nonzero(self):
        self.stub_osascript('echo DENY')
        self.assertNotEqual(self.run_askpass().returncode, 0)

    def test_a_broken_dialog_denies(self):
        # The whole safety argument. If osascript dies, is unavailable, or the user
        # dismisses the window, the answer must be NO.
        self.stub_osascript('exit 3')
        self.assertNotEqual(self.run_askpass().returncode, 0)

    def test_empty_output_denies(self):
        self.stub_osascript('true')
        self.assertNotEqual(self.run_askpass().returncode, 0)

    def test_unexpected_output_denies(self):
        # Anything that is not exactly ALLOW is a denial, so a localisation change
        # or a stray newline can never be read as consent.
        for junk in ('echo yes', 'echo Autorizar', 'echo ALLOWED', 'echo allow'):
            with self.subTest(junk=junk):
                self.stub_osascript(junk)
                self.assertNotEqual(self.run_askpass().returncode, 0)


class PassphraseMode(AskpassCase):
    """Without SSH_ASKPASS_PROMPT=confirm the agent reads STDOUT, not the status."""

    def test_the_passphrase_goes_to_stdout(self):
        self.stub_osascript('echo hunter2')
        out = self.run_askpass(confirm=False)
        self.assertEqual(out.stdout.strip(), "hunter2")

    def test_confirmation_mode_never_prints_a_button_name(self):
        # Getting the two modes backwards would feed a button label in as a
        # passphrase. Confirmation mode must stay silent on stdout.
        self.stub_osascript('echo ALLOW')
        self.assertEqual(self.run_askpass().stdout.strip(), "")


class TheScriptItself(unittest.TestCase):

    def test_it_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), "chmod +x askpass_macos.sh")

    def test_it_is_valid_posix_shell(self):
        r = subprocess.run(["/bin/sh", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    @staticmethod
    def code_only(src):
        """Strip comments before scanning.

        A first version of this test scanned the raw source and failed on the word
        `ssh-add` appearing in the script's own explanatory header. That is defect
        GUARD-MENTION-C, already on this project's register: a substring scan
        cannot tell a mention from a call. The registry's own rule is to check the
        code, so the comments come off first.
        """
        out = []
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            out.append(line.split(" #", 1)[0])
        return "\n".join(out)

    def test_it_holds_no_secret_and_reaches_no_network(self):
        code = self.code_only(SCRIPT.read_text(encoding="utf-8"))
        for forbidden in ("curl", "wget", "ssh-add", "ssh-keygen",
                          "PRIVATE KEY", "id_ed25519", "harness_root"):
            self.assertNotIn(forbidden, code,
                             "{} appears in executable code, not just prose".format(forbidden))

    def test_it_writes_no_file(self):
        # A helper invoked with the operator's key in play must not persist anything.
        code = self.code_only(SCRIPT.read_text(encoding="utf-8"))
        self.assertNotIn(">>", code)
        self.assertNotIn("tee", code)


if __name__ == "__main__":
    unittest.main()
