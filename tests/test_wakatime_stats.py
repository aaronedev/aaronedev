from __future__ import annotations

import base64
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.wakatime_stats import (  # noqa: E402
    WakaCollectionError,
    render,
    retrieve,
)

CANARY_VV = "Violet-Void/private-client-project"
CANARY_BF = "bauerstischfinder/top-secret-acquisition"
WAKA_URL = "https://wakatime.com/api/v1/users/current/stats/last_7_days"


def _stats_payload(*, include_canary_project: bool = True) -> dict:
    projects = []
    if include_canary_project:
        projects = [
            {
                "name": CANARY_VV,
                "text": "12 hrs 10 mins",
                "percent": 40.0,
                "hours": 12,
                "minutes": 10,
            },
            {
                "name": CANARY_BF,
                "text": "8 hrs",
                "percent": 20.0,
                "hours": 8,
                "minutes": 0,
            },
        ]
    return {
        "data": {
            "timezone": "Europe/Berlin",
            "languages": [
                {
                    "name": "Python",
                    "text": "10 hrs 5 mins",
                    "percent": 62.5,
                    "hours": 10,
                    "minutes": 5,
                },
                {
                    "name": "Markdown",
                    "text": "4 hrs",
                    "percent": 25.0,
                    "hours": 4,
                    "minutes": 0,
                },
                {
                    "name": "Shell",
                    "text": "2 hrs",
                    "percent": 12.5,
                    "hours": 2,
                    "minutes": 0,
                },
            ],
            "editors": [
                {
                    "name": "Neovim",
                    "text": "12 hrs",
                    "percent": 75.0,
                    "hours": 12,
                    "minutes": 0,
                },
                {
                    "name": "Opencode Cli",
                    "text": "4 hrs",
                    "percent": 25.0,
                    "hours": 4,
                    "minutes": 0,
                },
            ],
            "operating_systems": [
                {
                    "name": "Linux",
                    "text": "16 hrs",
                    "percent": 100.0,
                    "hours": 16,
                    "minutes": 0,
                }
            ],
            "projects": projects,
        }
    }


class WakaRetrieveTest(unittest.TestCase):
    def test_auth_is_basic_and_key_stays_out_of_url(self) -> None:
        seen = {}

        def http(url, *, method="GET", headers=None, json_body=None):
            seen["url"] = url
            seen["method"] = method
            seen["headers"] = headers
            return {"status": 200, "json": _stats_payload()}

        retrieve(http, api_key="waka-secret")
        self.assertEqual(seen["url"], WAKA_URL)
        self.assertEqual(seen["method"], "GET")
        self.assertNotIn("waka-secret", seen["url"])
        expected = "Basic " + base64.b64encode(b"waka-secret:").decode("ascii")
        self.assertEqual(seen["headers"]["Authorization"], expected)

    def test_http_error_raises(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 401, "json": {"error": "nope"}}

        with self.assertRaises(WakaCollectionError):
            retrieve(http, api_key="waka-secret")

    def test_malformed_payload_raises(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": {"unexpected": True}}

        with self.assertRaises(WakaCollectionError):
            retrieve(http, api_key="waka-secret")


class WakaRenderTest(unittest.TestCase):
    def test_canary_project_names_are_not_emitted(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": _stats_payload(include_canary_project=True)}

        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            stats = retrieve(http, api_key="waka-secret")
            markdown = render(stats)
        self.assertNotIn(CANARY_VV, markdown)
        self.assertNotIn(CANARY_BF, markdown)
        self.assertNotIn("private-client-project", markdown)
        self.assertNotIn("top-secret-acquisition", markdown)
        self.assertNotIn("Projects:", markdown)
        self.assertNotIn(CANARY_VV, buf.getvalue())
        self.assertNotIn(CANARY_BF, buf.getvalue())

    def test_github_short_info_is_omitted(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": _stats_payload()}

        markdown = render(retrieve(http, api_key="waka-secret"))
        self.assertNotIn("Opted to Hire", markdown)
        self.assertNotIn("Private Repositories", markdown)
        self.assertNotIn("Used in Github's Storage", markdown)
        self.assertNotIn("My Github Data", markdown)
        self.assertNotIn("I Mostly Code in", markdown)

    def test_includes_timezone_languages_editors_os_with_bars(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": _stats_payload()}

        markdown = render(retrieve(http, api_key="waka-secret"))
        self.assertIn("Europe/Berlin", markdown)
        self.assertIn("Python", markdown)
        self.assertIn("Neovim", markdown)
        self.assertIn("Linux", markdown)
        self.assertIn("█", markdown)
        self.assertIn("░", markdown)
        self.assertIn("62.5%", markdown)

    def test_commit_aggregates_injected_only_when_provided(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": _stats_payload()}

        stats = retrieve(http, api_key="waka-secret")
        without_timing = render(stats)
        self.assertNotIn("Morning", without_timing)
        self.assertNotIn("Most Productive", without_timing)

        with_timing = render(
            stats,
            commit_hours={"morning": 10, "daytime": 2, "evening": 1, "night": 0},
            commit_weekdays={
                "Monday": 8,
                "Tuesday": 1,
                "Wednesday": 0,
                "Thursday": 2,
                "Friday": 1,
                "Saturday": 0,
                "Sunday": 1,
            },
        )
        self.assertIn("Morning", with_timing)
        self.assertIn("Most Productive on Monday", with_timing)
        self.assertIn("█", with_timing)

    def test_render_is_deterministic(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": _stats_payload()}

        stats = retrieve(http, api_key="waka-secret")
        self.assertEqual(render(stats), render(stats))


if __name__ == "__main__":
    unittest.main()
