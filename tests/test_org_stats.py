from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.org_stats import Stats, StatsError, collect, main, publish, render_languages, render_overview


def repo(name: str, *, private=False, fork=False, archived=False, stars=0, pushed="2026-11-01T00:00:00Z") -> dict:
    return {
        "full_name": f"Violet-Void/{name}", "name": name,
        "private": private, "fork": fork, "archived": archived,
        "stargazers_count": stars, "pushed_at": pushed,
    }


class OrgStatsTest(unittest.TestCase):
    def setUp(self):
        self.repos = [
            repo("dotfiles", private=True, stars=0),
            repo("public-tool", stars=7),
            repo("fork-copy", fork=True),
            repo("old", archived=True),
        ]
        self.calls = []

    def fetch(self, path: str):
        self.calls.append(path)
        if path.startswith("/orgs/"):
            return self.repos
        if path.endswith("/dotfiles/languages"):
            return {"Python": 600, "Shell": 300}
        if path.endswith("/public-tool/languages"):
            return {"Rust": 100}
        self.fail(f"Unexpected request {path}")

    def test_private_code_is_counted_without_importing_forks(self):
        result = collect(self.fetch, now=datetime(2026, 11, 4, tzinfo=timezone.utc))
        self.assertEqual((result.repositories, result.public, result.private, result.stars), (2, 1, 1, 7))
        self.assertEqual(result.pushed_90d, 2)
        self.assertEqual(result.languages, {"Python": 600, "Shell": 300, "Rust": 100})
        self.assertEqual(len([p for p in self.calls if p.endswith("/languages")]), 2)
        for card in (render_overview(result), render_languages(result)):
            ET.fromstring(card)
            self.assertNotIn("dotfiles", card)
            self.assertNotIn("public-tool", card)

    def test_missing_private_access_fails_closed(self):
        self.repos = [repo("public-tool")]
        with self.assertRaisesRegex(StatsError, "required private"):
            collect(self.fetch)
        self.assertEqual(len(self.calls), 1)

    def test_api_error_does_not_replace_published_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for filename in ("violet-void-org-stats.svg", "violet-void-org-languages.svg"):
                (path / filename).write_text("KNOWN GOOD", encoding="utf-8")
            with patch("scripts.org_stats.urlopen", side_effect=URLError("simulated outage")) as request:
                self.assertEqual(
                    main(["--output-dir", str(path)], environ={"README_ORG_STATS_TOKEN": "dummy-token"}), 2
                )
            request.assert_called_once()
            for filename in ("violet-void-org-stats.svg", "violet-void-org-languages.svg"):
                self.assertEqual((path / filename).read_text(), "KNOWN GOOD")

    def test_unknown_language_escaped_and_aggregated(self):
        stats = Stats(2, 1, 1, 7, 2, {"Rust & <other>": 1, "Shell": 9})
        svg = render_languages(stats)
        ET.fromstring(svg)
        self.assertIn("Rust &amp; &lt;other&gt;", svg)
        self.assertIn("90.0%", svg)

    def test_publish_deterministic(self):
        stats = collect(self.fetch)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            publish(dest, stats)
            originals = [(dest / name).read_bytes() for name in ("violet-void-org-stats.svg", "violet-void-org-languages.svg")]
            publish(dest, stats)
            self.assertEqual(originals, [(dest / name).read_bytes() for name in ("violet-void-org-stats.svg", "violet-void-org-languages.svg")])

    def test_rejects_incomplete_language_data(self):
        def bad(path):
            if path.endswith("/languages"):
                return {"Python": "600"}
            return self.repos
        with self.assertRaisesRegex(StatsError, "languages"):
            collect(bad)

    def test_pagination_and_empty_language_data(self):
        org_page = [repo("dotfiles", private=True)] + [repo(f"project-{i:03}") for i in range(99)]
        def fetch(path):
            if "&page=1" in path:
                return org_page
            if "&page=2" in path:
                return [repo("last")]
            if path.endswith("/languages"):
                return {}
            self.fail(path)
        result = collect(fetch)
        self.assertEqual(result.repositories, 101)
        self.assertEqual(render_languages(result).count("No language bytes reported"), 1)


if __name__ == "__main__":
    unittest.main()
