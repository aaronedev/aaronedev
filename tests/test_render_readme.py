from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.readme_config import (  # noqa: E402
    ACTIVITY_END,
    ACTIVITY_START,
    ALLOWED_OWNERS,
    WAKA_END,
    WAKA_START,
)
from scripts.render_readme import (  # noqa: E402
    EXIT_COLLECTOR_FAILED,
    EXIT_OK,
    WAKA_FALLBACK,
    _collect_activity,
    _atomic_write,
    main,
    render_readme,
)
from scripts.wakatime_stats import WAKA_SECTION_MARKER, render as render_waka  # noqa: E402

CANARY_VV = "Violet-Void/private-client-project"
CANARY_BF = "bauerstischfinder/top-secret-acquisition"

TEMPLATE = """# profile

## ⭐ Recent activity

<details>
  <summary><strong>Click to expand recent GitHub activity</strong></summary>

{activity_start}
{activity_end}

</details>

### ✨ WakaTime stats ✨
<details>
  <summary>Click to expand the latest metrics</summary>

{waka_start}
{waka_end}

</details>
""".format(
    activity_start=ACTIVITY_START,
    activity_end=ACTIVITY_END,
    waka_start=WAKA_START,
    waka_end=WAKA_END,
)


def _activity_fixture() -> dict:
    pull_requests = []
    contributions = []
    for owner in ALLOWED_OWNERS:
        repo = f"{owner}/public-demo"
        pull_requests.append(
            {
                "title": f"{owner} demo pr",
                "url": f"https://github.com/{repo}/pull/1",
                "state": "MERGED",
                "createdAt": "2026-08-20T15:00:00Z",
                "repository": {
                    "nameWithOwner": repo,
                    "isPrivate": False,
                    "url": f"https://github.com/{repo}",
                    "description": f"{owner} public demo",
                    "owner": {"login": owner},
                },
            }
        )
        contributions.append(
            {
                "contributionCount": 2,
                "repository": {
                    "nameWithOwner": repo,
                    "isPrivate": False,
                    "url": f"https://github.com/{repo}",
                    "description": f"{owner} public demo",
                    "owner": {"login": owner},
                },
            }
        )
    vv_owner, vv_name = CANARY_VV.split("/", 1)
    bf_owner, bf_name = CANARY_BF.split("/", 1)
    pull_requests.append(
        {
            "title": "should not leak",
            "url": f"https://github.com/{CANARY_VV}/pull/1",
            "state": "OPEN",
            "createdAt": "2026-08-19T15:00:00Z",
            "repository": {
                "nameWithOwner": CANARY_VV,
                "isPrivate": True,
                "url": f"https://github.com/{CANARY_VV}",
                "description": "secret",
                "owner": {"login": vv_owner},
            },
        }
    )
    contributions.append(
        {
            "contributionCount": 6,
            "repository": {
                "nameWithOwner": CANARY_BF,
                "isPrivate": True,
                "url": f"https://github.com/{CANARY_BF}",
                "description": "secret",
                "owner": {"login": bf_owner},
            },
        }
    )
    return {"pull_requests": pull_requests, "contributions": contributions}


def _waka_fixture() -> dict:
    return {
        "data": {
            "timezone": "Europe/Berlin",
            "languages": [
                {
                    "name": "Python",
                    "text": "3 hrs",
                    "percent": 100.0,
                    "hours": 3,
                    "minutes": 0,
                }
            ],
            "editors": [
                {
                    "name": "Neovim",
                    "text": "3 hrs",
                    "percent": 100.0,
                    "hours": 3,
                    "minutes": 0,
                }
            ],
            "operating_systems": [
                {
                    "name": "Linux",
                    "text": "3 hrs",
                    "percent": 100.0,
                    "hours": 3,
                    "minutes": 0,
                }
            ],
            "projects": [
                {
                    "name": CANARY_VV,
                    "text": "3 hrs",
                    "percent": 100.0,
                    "hours": 3,
                    "minutes": 0,
                }
            ],
        }
    }


def _write_repo(tmp: Path, *, readme: str | None = None) -> Path:
    (tmp / "templates").mkdir()
    (tmp / "templates" / "README.md.tpl").write_text(TEMPLATE, encoding="utf-8")
    if readme is not None:
        (tmp / "README.md").write_text(readme, encoding="utf-8")
    return tmp


def _section(text: str, start: str, end: str) -> str:
    left = text.index(start) + len(start)
    right = text.index(end)
    return text[left:right]


class RenderReadmeTest(unittest.TestCase):
    def test_github_failure_preserves_tagged_waka_even_when_waka_succeeds(self) -> None:
        previous_waka = "\n" + render_waka(
            {"timezone": "Europe/Berlin", "languages": [], "editors": [], "operating_systems": []}
        )
        existing = TEMPLATE.replace(
            f"{WAKA_START}\n{WAKA_END}", f"{WAKA_START}{previous_waka}{WAKA_END}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp), readme=existing)
            waka_path = root / "waka.json"
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            code = main(["--repo-root", str(root), "--fixture-waka", str(waka_path)], environ={})
            self.assertEqual(code, EXIT_COLLECTOR_FAILED)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertEqual(_section(readme, WAKA_START, WAKA_END), previous_waka)

    def test_waka_failure_preserves_only_tagged_current_section(self) -> None:
        previous_waka = f"\n{WAKA_SECTION_MARKER}\nTAGGED-PREVIOUS-WAKA\n"
        existing = TEMPLATE.replace(
            f"{WAKA_START}\n{WAKA_END}", f"{WAKA_START}{previous_waka}{WAKA_END}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp), readme=existing)
            activity_path = root / "activity.json"
            activity_path.write_text(json.dumps(_activity_fixture()), encoding="utf-8")
            code = main(
                ["--repo-root", str(root), "--fixture-activity", str(activity_path)],
                environ={},
            )
            self.assertEqual(code, EXIT_COLLECTOR_FAILED)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertEqual(_section(readme, WAKA_START, WAKA_END), previous_waka)

    def test_github_failure_rejects_legacy_waka_even_when_waka_succeeds(self) -> None:
        legacy_waka = "\n**Projects:**\n- legacy-private-project\n"
        existing = TEMPLATE.replace(
            f"{WAKA_START}\n{WAKA_END}", f"{WAKA_START}{legacy_waka}{WAKA_END}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp), readme=existing)
            waka_path = root / "waka.json"
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            code = main(["--repo-root", str(root), "--fixture-waka", str(waka_path)], environ={})
            self.assertEqual(code, EXIT_COLLECTOR_FAILED)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertEqual(_section(readme, WAKA_START, WAKA_END), WAKA_FALLBACK)

    def test_zero_result_success_uses_empty_strings_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            activity_path = root / "activity.json"
            waka_path = root / "waka.json"
            activity_path.write_text(
                json.dumps({"pull_requests": [], "contributions": []}),
                encoding="utf-8",
            )
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--fixture-activity",
                    str(activity_path),
                    "--fixture-waka",
                    str(waka_path),
                ]
            )
            self.assertEqual(code, EXIT_OK)
            readme = (root / "README.md").read_text(encoding="utf-8")
            activity = _section(readme, ACTIVITY_START, ACTIVITY_END)
            self.assertIn("_No public pull requests from allowed owners._", activity)
            self.assertIn("_No public commits from allowed owners._", activity)
            self.assertNotIn("_Activity temporarily unavailable._", activity)

    def test_readme_activity_github_pat_is_preferred_token(self) -> None:
        captured: list[str] = []

        def fake_retrieve(_http, token: str):
            captured.append(token)
            return _activity_fixture()

        with patch("scripts.render_readme.retrieve_activity", fake_retrieve):
            _collect_activity(
                None,
                {
                    "README_ACTIVITY_GITHUB_PAT": "purpose-pat",
                    "GH_TOKEN": "generic-gh",
                    "GITHUB_TOKEN": "builtin",
                },
            )
        self.assertEqual(captured, ["purpose-pat"])

    def test_github_failure_preserves_previous_activity_bytes(self) -> None:
        previous_activity = "\nPREVIOUS-ACTIVITY-BYTES\n"
        previous_waka = "\nPREVIOUS-WAKA-BYTES\n"
        existing = TEMPLATE.replace(
            f"{ACTIVITY_START}\n{ACTIVITY_END}",
            f"{ACTIVITY_START}{previous_activity}{ACTIVITY_END}",
        ).replace(
            f"{WAKA_START}\n{WAKA_END}",
            f"{WAKA_START}{previous_waka}{WAKA_END}",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp), readme=existing)
            waka_path = root / "waka.json"
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            env = os.environ.copy()
            env.pop("README_ACTIVITY_GITHUB_PAT", None)
            env.pop("GH_TOKEN", None)
            env.pop("GITHUB_TOKEN", None)
            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--fixture-waka",
                    str(waka_path),
                ],
                environ=env,
            )
            self.assertEqual(code, EXIT_COLLECTOR_FAILED)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertEqual(
                _section(readme, ACTIVITY_START, ACTIVITY_END),
                previous_activity,
            )
            self.assertNotIn("_No public pull requests from allowed owners._", readme)

    def test_waka_failure_replaces_legacy_private_section_with_fallback(self) -> None:
        previous_activity = "\nkept-activity\n"
        previous_waka = (
            "\n**Projects:**\n"
            f"- {CANARY_VV}\n"
            f"- {CANARY_BF}\n"
            "- private project name\n"
        )
        existing = TEMPLATE.replace(
            f"{ACTIVITY_START}\n{ACTIVITY_END}",
            f"{ACTIVITY_START}{previous_activity}{ACTIVITY_END}",
        ).replace(
            f"{WAKA_START}\n{WAKA_END}",
            f"{WAKA_START}{previous_waka}{WAKA_END}",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp), readme=existing)
            activity_path = root / "activity.json"
            activity_path.write_text(json.dumps(_activity_fixture()), encoding="utf-8")
            env = os.environ.copy()
            env.pop("README_WAKATIME_API_KEY", None)
            env.pop("WAKATIME_API_KEY", None)
            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--fixture-activity",
                    str(activity_path),
                ],
                environ=env,
            )
            self.assertEqual(code, EXIT_COLLECTOR_FAILED)
            readme = (root / "README.md").read_text(encoding="utf-8")
            waka = _section(readme, WAKA_START, WAKA_END)
            self.assertEqual(waka, WAKA_FALLBACK)
            self.assertIn(WAKA_FALLBACK, readme)
            self.assertNotIn("Projects:", waka)
            self.assertNotIn(CANARY_VV, waka)
            self.assertNotIn(CANARY_BF, waka)
            self.assertNotIn("private project name", waka)

    def test_missing_previous_section_uses_stable_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            env = os.environ.copy()
            env.pop("README_ACTIVITY_GITHUB_PAT", None)
            env.pop("GH_TOKEN", None)
            env.pop("GITHUB_TOKEN", None)
            env.pop("README_WAKATIME_API_KEY", None)
            env.pop("WAKATIME_API_KEY", None)
            code = main(["--repo-root", str(root)], environ=env)
            self.assertEqual(code, EXIT_COLLECTOR_FAILED)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("_Activity temporarily unavailable._", readme)
            self.assertNotIn("_No public pull requests from allowed owners._", readme)
            self.assertNotIn("No activity", readme)

    def test_canaries_absent_from_generated_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            activity_path = root / "activity.json"
            waka_path = root / "waka.json"
            activity_path.write_text(json.dumps(_activity_fixture()), encoding="utf-8")
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--fixture-activity",
                    str(activity_path),
                    "--fixture-waka",
                    str(waka_path),
                ]
            )
            self.assertEqual(code, EXIT_OK)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertNotIn(CANARY_VV, readme)
            self.assertNotIn(CANARY_BF, readme)
            self.assertNotIn("private-client-project", readme)
            self.assertNotIn("top-secret-acquisition", readme)
            self.assertIn(ACTIVITY_START, readme)
            self.assertIn(WAKA_START, readme)
            for owner in ALLOWED_OWNERS:
                self.assertIn(f"{owner}/public-demo", readme)
            self.assertIn("🔒 Private activity:", readme)
            self.assertIn("Python", readme)
            self.assertNotIn("Projects:", readme)
            waka = _section(readme, WAKA_START, WAKA_END)
            self.assertEqual(waka.count(WAKA_SECTION_MARKER), 1)
            self.assertEqual(waka.count("```"), 2)

    def test_double_fixture_render_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            activity_path = root / "activity.json"
            waka_path = root / "waka.json"
            activity_path.write_text(json.dumps(_activity_fixture()), encoding="utf-8")
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            args = [
                "--repo-root",
                str(root),
                "--fixture-activity",
                str(activity_path),
                "--fixture-waka",
                str(waka_path),
            ]
            self.assertEqual(main(args), EXIT_OK)
            first = (root / "README.md").read_bytes()
            self.assertEqual(main(args), EXIT_OK)
            second = (root / "README.md").read_bytes()
            self.assertEqual(first, second)

    def test_cli_subprocess_double_render_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            activity_path = root / "activity.json"
            waka_path = root / "waka.json"
            out_a = root / "out-a.md"
            out_b = root / "out-b.md"
            activity_path.write_text(json.dumps(_activity_fixture()), encoding="utf-8")
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            script = ROOT / "scripts" / "render_readme.py"
            common = [
                sys.executable,
                str(script),
                "--repo-root",
                str(root),
                "--fixture-activity",
                str(activity_path),
                "--fixture-waka",
                str(waka_path),
            ]
            first = subprocess.run(
                [*common, "--output", str(out_a)],
                check=False,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                [*common, "--output", str(out_b)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, EXIT_OK, first.stderr)
            self.assertEqual(second.returncode, EXIT_OK, second.stderr)
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())
            self.assertNotIn(CANARY_VV, out_a.read_text(encoding="utf-8"))
            self.assertNotIn(CANARY_BF, out_a.read_text(encoding="utf-8"))

    def test_render_readme_helper_uses_injected_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            text = render_readme(
                root,
                activity_markdown="ACTIVITY-BODY",
                waka_markdown="WAKA-BODY",
            )
            self.assertIn("ACTIVITY-BODY", text)
            self.assertIn("WAKA-BODY", text)
            self.assertEqual(text.count(ACTIVITY_START), 1)
            self.assertEqual(text.count(WAKA_START), 1)

    def test_atomic_write_preserves_existing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "README.md"
            path.write_text("old", encoding="utf-8")
            path.chmod(0o640)
            _atomic_write(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_main_routes_selected_sections_through_render_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            activity_path = root / "activity.json"
            waka_path = root / "waka.json"
            activity_path.write_text(json.dumps(_activity_fixture()), encoding="utf-8")
            waka_path.write_text(json.dumps(_waka_fixture()), encoding="utf-8")
            with patch(
                "scripts.render_readme.render_readme", wraps=render_readme
            ) as renderer:
                code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--fixture-activity",
                        str(activity_path),
                        "--fixture-waka",
                        str(waka_path),
                    ]
                )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(renderer.call_count, 1)
            self.assertIn(
                "aaronedev/public-demo",
                renderer.call_args.kwargs["activity_markdown"],
            )
            self.assertIn("Python", renderer.call_args.kwargs["waka_markdown"])


if __name__ == "__main__":
    unittest.main()
