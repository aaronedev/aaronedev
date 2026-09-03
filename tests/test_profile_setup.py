from __future__ import annotations

import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.readme_config import ACTIVITY_END, ACTIVITY_START, WAKA_END, WAKA_START
from scripts.profile_setup import (
    PROFILE_END,
    PROFILE_START,
    ProfileAnswers,
    ProfilePaths,
    ProfileSetupError,
    apply_profile_setup,
    main,
    render_profile,
    validate_answers,
)


ROOT = Path(__file__).resolve().parents[1]


class ProfileSetupTest(unittest.TestCase):
    def _paths(self, root: Path) -> ProfilePaths:
        config = root / "scripts" / "readme_config.py"
        template = root / "templates" / "README.md.tpl"
        readme = root / "README.md"
        workflow = root / ".github" / "workflows" / "readme.yaml"
        config.parent.mkdir(parents=True)
        template.parent.mkdir(parents=True)
        workflow.parent.mkdir(parents=True)
        shutil.copy(ROOT / "scripts" / "readme_config.py", config)
        shutil.copy(ROOT / "templates" / "README.md.tpl", template)
        shutil.copy(ROOT / "README.md", readme)
        shutil.copy(ROOT / ".github" / "workflows" / "readme.yaml", workflow)
        return ProfilePaths(config=config, template=template, readme=readme, workflow=workflow)

    @staticmethod
    def _answers(**overrides) -> ProfileAnswers:
        values = {
            "display_name": "Example Builder",
            "github_login": "example-builder",
            "what_i_build": "privacy-respecting developer tools",
            "intro": "",
            "focus_items": ("Ship a CLI", "Write docs", "Review feedback"),
            "help_items": ("Python", "Documentation", "Developer tooling"),
            "timezone": "Europe/Berlin",
            "project_owners": ("example-builder", "example-lab"),
            "use_ubuntu_runner": True,
        }
        values.update(overrides)
        return ProfileAnswers(**values)

    def test_apply_updates_only_the_bounded_profile_and_config_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            config = paths.config
            template = paths.template
            readme = paths.readme
            workflow = paths.workflow
            original_template = template.read_text()
            original_readme = readme.read_text()

            apply_profile_setup(
                paths,
                self._answers(),
            )

            self.assertIn('AUTHOR_LOGIN = "example-builder"', config.read_text())
            self.assertIn('PROFILE_REPO = "example-builder/example-builder"', config.read_text())
            self.assertIn('ALLOWED_OWNERS = ("example-builder", "example-lab")', config.read_text())
            self.assertIn('PROFILE_TIMEZONE = "Europe/Berlin"', config.read_text())
            self.assertIn('runs-on: ubuntu-latest', workflow.read_text())
            template_text = template.read_text()
            readme_text = readme.read_text()
            self.assertIn("<h1 align=\"center\">Example Builder / example-builder</h1>", template_text)
            self.assertIn("## What I build", template_text)
            self.assertIn("## ⭐ Recent activity", template_text)
            self.assertEqual(
                template_text.split("<!--START_SECTION:profile-->", 1)[1].split(
                    "<!--END_SECTION:profile-->", 1
                )[0],
                readme_text.split("<!--START_SECTION:profile-->", 1)[1].split(
                    "<!--END_SECTION:profile-->", 1
                )[0],
            )
            self.assertEqual(
                template_text.split("<!--START_SECTION:profile-->", 1)[0],
                original_template.split("<!--START_SECTION:profile-->", 1)[0],
            )
            self.assertEqual(
                self._without_dynamic_sections(
                    template_text.split("<!--END_SECTION:profile-->", 1)[1]
                ),
                self._without_dynamic_sections(
                    original_template.split("<!--END_SECTION:profile-->", 1)[1]
                ),
            )
            self.assertEqual(
                readme_text.split("<!--START_SECTION:profile-->", 1)[0],
                original_readme.split("<!--START_SECTION:profile-->", 1)[0],
            )
            self.assertEqual(
                self._without_dynamic_sections(
                    readme_text.split("<!--END_SECTION:profile-->", 1)[1]
                ),
                self._without_dynamic_sections(
                    original_readme.split("<!--END_SECTION:profile-->", 1)[1]
                ),
            )

    @staticmethod
    def _without_dynamic_sections(text: str) -> str:
        for start, end in ((ACTIVITY_START, ACTIVITY_END), (WAKA_START, WAKA_END)):
            start_at = text.index(start) + len(start)
            end_at = text.index(end)
            text = text[:start_at] + text[end_at:]
        return text

    def test_defaults_and_html_escaping_are_safe(self) -> None:
        answers = validate_answers(
            self._answers(
                display_name="<Example & Builder>",
                what_i_build="<tools & docs>",
                focus_items=(),
                help_items=(),
            )
        )
        profile = render_profile(answers)

        self.assertIn("&lt;Example &amp; Builder&gt;", profile)
        self.assertIn("&lt;tools &amp; docs&gt;", profile)
        self.assertEqual(profile.count("\n- "), 7)
        self.assertIn("Build a small public project", profile)
        self.assertIn("Software design", profile)

    def test_invalid_timezone_fails_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            before = {path: path.read_bytes() for path in (paths.config, paths.template, paths.readme)}

            for timezone in ("Not/A_Timezone", "Europe//Berlin"):
                with self.subTest(timezone=timezone):
                    with self.assertRaises(ProfileSetupError):
                        apply_profile_setup(paths, self._answers(timezone=timezone))

            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_apply_neutralizes_inherited_dynamic_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            for path in (paths.template, paths.readme):
                text = path.read_text(encoding="utf-8")
                text = text.replace(
                text = text.replace(
                    ACTIVITY_START,
                    f"{ACTIVITY_START}\nupstream activity",
                )
                text = text.replace(
                    WAKA_START,
                    f"{WAKA_START}\nupstream waka",
                )

            apply_profile_setup(paths, self._answers(use_ubuntu_runner=False))

            for path in (paths.template, paths.readme):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("upstream activity", text)
                self.assertNotIn("upstream waka", text)
                self.assertIn("Activity will appear after you run the README workflow.", text)
                self.assertIn("WakaTime stats will appear after you run the README workflow.", text)

    def test_apply_restores_every_file_and_mode_when_a_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            targets = (paths.config, paths.template, paths.readme, paths.workflow)
            for index, path in enumerate(targets):
                path.chmod(0o600 + index)
            before = {
                path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) for path in targets
            }
            from scripts import profile_setup

            original_write = profile_setup._atomic_write
            writes = 0

            def fail_second_write(path: Path, text: str) -> None:
                nonlocal writes
                writes += 1
                if writes == 2:
                    raise OSError("simulated write failure")
                original_write(path, text)

            with patch("scripts.profile_setup._atomic_write", side_effect=fail_second_write):
                with self.assertRaises(OSError):
                    apply_profile_setup(paths, self._answers())

            self.assertEqual(
                {
                    path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
                    for path in targets
                },
                before,
            )

    def test_single_default_owner_stays_a_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            apply_profile_setup(
                paths,
                self._answers(project_owners=(), use_ubuntu_runner=False),
            )

            self.assertIn('ALLOWED_OWNERS = ("example-builder",)', paths.config.read_text())

    def test_marker_tokens_and_invalid_boundaries_fail_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            before = {path: path.read_text() for path in (paths.config, paths.template, paths.readme)}
            with self.assertRaises(ProfileSetupError):
                validate_answers(self._answers(intro=f"safe {PROFILE_START}"))
            paths.template.write_text(paths.template.read_text().replace(PROFILE_START, "", 1))
            with self.assertRaises(ProfileSetupError):
                apply_profile_setup(paths, self._answers())

            self.assertEqual(paths.config.read_text(), before[paths.config])
            self.assertEqual(paths.readme.read_text(), before[paths.readme])

    def test_duplicate_assignment_and_markers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            paths.config.write_text(paths.config.read_text() + '\nAUTHOR_LOGIN = "duplicate"\n')
            paths.readme.write_text(paths.readme.read_text().replace(PROFILE_END, PROFILE_END * 2, 1))
            before = {path: path.read_text() for path in (paths.config, paths.template, paths.readme)}

            with self.assertRaises(ProfileSetupError):
                apply_profile_setup(paths, self._answers())

            self.assertEqual(
                {path: path.read_text() for path in before},
                before,
            )

    def test_inverted_markers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            before_start, remainder = paths.template.read_text().split(PROFILE_START, 1)
            profile, after_end = remainder.split(PROFILE_END, 1)
            paths.template.write_text(before_start + PROFILE_END + profile + PROFILE_START + after_end)
            before = paths.template.read_text()

            with self.assertRaises(ProfileSetupError):
                apply_profile_setup(paths, self._answers())

            self.assertEqual(paths.template.read_text(), before)

    def test_check_is_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            before = {
                path: path.read_bytes()
                for path in (paths.config, paths.template, paths.readme, paths.workflow)
            }

            self.assertEqual(main(["--check", "--repo-root", str(root)]), 0)

            self.assertEqual(
                {path: path.read_bytes() for path in before},
                before,
            )


if __name__ == "__main__":
    unittest.main()
