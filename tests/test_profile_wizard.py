from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIZARD = ROOT / "bin" / "setup-profile"


class ProfileWizardTest(unittest.TestCase):
    def test_wizard_is_syntax_valid_and_has_authored_stages(self) -> None:
        subprocess.run(["bash", "-n", str(WIZARD)], check=True)
        authored = WIZARD.read_text(encoding="utf-8").split(
            "# STAGES: author this section only.", 1
        )[1]

        self.assertIn('WIZARD_ID="fork-profile-setup"', authored)
        self.assertIn('WIZARD_TITLE="Fork profile setup"', authored)
        self.assertNotIn("Replace this", authored)
        self.assertNotIn("unconfigured", authored)

    def test_plan_is_the_default_and_does_not_require_live_tools(self) -> None:
        result = subprocess.run(
            [str(WIZARD), "--plan"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plan only: no prompts, files, commands, remote writes, or state changes.", result.stdout)
        self.assertIn("Verify this checkout is a GitHub fork", result.stdout)
        self.assertIn("Offer optional Copilot text drafting", result.stdout)

    def test_apply_refuses_a_non_fork_before_creating_state_or_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_bin = root / "fake-bin"
            state_dir = root / "state"
            setup = root / "bin" / "setup-profile"
            fake_bin.mkdir()
            setup.parent.mkdir()
            shutil.copy(WIZARD, setup)
            setup.chmod(setup.stat().st_mode | stat.S_IXUSR)
            sentinel = root / "README.md"
            sentinel.write_text("unchanged\n", encoding="utf-8")
            self._fake_command(
                fake_bin / "git",
                "#!/usr/bin/env bash\nprintf '%s\\n' 'https://github.com/example/not-a-fork.git'\n",
            )
            self._fake_command(
                fake_bin / "gh",
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == auth ]]; then exit 0; fi\n"
                "if [[ \"$*\" == *'nameWithOwner'* ]]; then printf '%s\\n' 'example/not-a-fork'; exit 0; fi\n"
                "if [[ \"$*\" == *'isFork'* ]]; then printf '%s\\n' 'false'; exit 0; fi\n"
                "exit 1\n",
            )
            environment = dict(os.environ)
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["WIZARD_STATE_DIR"] = str(state_dir)

            result = subprocess.run(
                [str(setup), "--apply"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("origin must be a GitHub fork", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged\n")
            self.assertFalse(state_dir.exists())

    @staticmethod
    def _fake_command(path: Path, contents: str) -> None:
        path.write_text(contents, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
