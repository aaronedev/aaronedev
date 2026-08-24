from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
    main,
    render_readme,
)

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

    def test_waka_failure_preserves_previous_waka_bytes(self) -> None:
        previous_activity = "\nkept-activity\n"
        previous_waka = "\nkept-waka\n"
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
            self.assertEqual(_section(readme, WAKA_START, WAKA_END), previous_waka)

    def test_missing_previous_section_uses_stable_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_repo(Path(tmp))
            env = os.environ.copy()
            env.pop("GH_TOKEN", None)
            env.pop("GITHUB_TOKEN", None)
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


if __name__ == "__main__":
    unittest.main()
