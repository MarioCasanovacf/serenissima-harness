"""Regression tests for safe_delete's path validation.

The `..`-control-plane-bypass fix must not follow symlinks: quarantining a link
must move the LINK (not its target), and a dangling link must stay deletable,
while the `..` bypass and workspace-escape protections must still hold.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BIN = str(Path(__file__).resolve().parents[1] / "bin")
sys.path.insert(0, BIN)  # so safe_delete can `import portalock`
_spec = importlib.util.spec_from_file_location("safe_delete", Path(BIN) / "safe_delete.py")
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


class SafeDeletePathValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safedel-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = Path(self.tmp).resolve()
        (self.root / ".harness").mkdir()
        (self.root / "projects").mkdir()
        (self.root / "projects" / "real.txt").write_text("IMPORTANT DATA")

    def test_symlink_validates_to_the_link_not_its_target(self):
        os.symlink("projects/real.txt", self.root / "alias.txt")
        named, relative = sd._validate(self.root, "alias.txt")
        self.assertEqual(named.name, "alias.txt",
                         "quarantine must act on the link, not the linked-to file")
        self.assertEqual(str(relative), "alias.txt")

    def test_quarantine_a_symlink_leaves_the_target_intact(self):
        os.symlink("projects/real.txt", self.root / "alias.txt")
        sd.quarantine(self.root, ["alias.txt"], reason="test")
        self.assertTrue((self.root / "projects" / "real.txt").exists(),
                        "the linked-to file must NOT be moved into quarantine")
        self.assertFalse((self.root / "alias.txt").exists(),
                         "the link itself must be gone (quarantined)")

    def test_dangling_symlink_is_quarantinable(self):
        os.symlink("nowhere.txt", self.root / "dangling.txt")
        named, _ = sd._validate(self.root, "dangling.txt")  # must not raise
        self.assertEqual(named.name, "dangling.txt")

    def test_dotdot_control_plane_bypass_still_blocked(self):
        with self.assertRaises(sd.SafetyError):
            sd._validate(self.root, "projects/../.harness/state.json")

    def test_symlink_escaping_workspace_still_blocked(self):
        os.symlink("/etc/hosts", self.root / "escape.txt")
        with self.assertRaises(sd.SafetyError):
            sd._validate(self.root, "escape.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
