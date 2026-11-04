"""Produce privacy-bounded SVG summaries of accessible Violet-Void source repositories.

Only aggregated counts and language names are published. No repository names, API
responses, credentials, or private URLs are written to the public profile.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ORG = "Violet-Void"
REQUIRED_REPO = "Violet-Void/dotfiles"
API_BASE = "https://api.github.com"
PAGE_SIZE = 100
MAX_PAGES = 20
OUTPUTS = ("violet-void-org-stats.svg", "violet-void-org-languages.svg")
ROOT = Path(__file__).resolve().parent.parent


class StatsError(Exception):
    """An incomplete or inaccessible source must not become public statistics."""


@dataclass(frozen=True)
class Stats:
    repositories: int
    public: int
    private: int
    stars: int
    pushed_90d: int
    languages: dict[str, int]


def github_fetch(token: str) -> Callable[[str], object]:
    def fetch(path: str) -> object:
        request = Request(
            API_BASE + path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "violet-void-profile-stats",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            raise StatsError(f"GitHub API returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise StatsError("GitHub API request or response failed") from None

    return fetch


def _pushed_recently(raw: object, now: datetime) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return timestamp.tzinfo is not None and timestamp >= now - timedelta(days=90)
    except ValueError:
        return False


def collect(fetch: Callable[[str], object], *, now: datetime | None = None) -> Stats:
    now = now or datetime.now(timezone.utc)
    repositories: list[dict] = []
    seen: set[str] = set()
    for page in range(1, MAX_PAGES + 1):
        data = fetch(f"/orgs/{ORG}/repos?type=all&sort=full_name&direction=asc&per_page={PAGE_SIZE}&page={page}")
        if not isinstance(data, list) or len(data) > PAGE_SIZE:
            raise StatsError("Unexpected organization repository response")
        for repo in data:
            if not isinstance(repo, dict) or not isinstance(repo.get("name"), str):
                raise StatsError("Unexpected repository metadata")
            full_name = repo.get("full_name")
            if not isinstance(full_name, str) or not full_name.casefold().startswith(ORG.casefold() + "/"):
                raise StatsError("Unexpected repository owner")
            if full_name.casefold() in seen:
                raise StatsError("Duplicate repository in organization pagination")
            seen.add(full_name.casefold())
            repositories.append(repo)
        if len(data) < PAGE_SIZE:
            break
    else:
        raise StatsError("Organization repository pagination limit reached")

    # Prevent publishing public-only percentages when the PAT cannot see the
    # primary private repository. Never silently claim partial data is complete.
    if not any(r.get("full_name", "").casefold() == REQUIRED_REPO.casefold() and r.get("private") is True for r in repositories):
        raise StatsError("Statistics token cannot access the required private organization repository")

    # Exclude imported forks and archived code from the organization's current
    # code mix; all remaining accessible repositories, public and private, count.
    sources = [r for r in repositories if r.get("fork") is False and r.get("archived") is False]
    language_bytes: Counter[str] = Counter()
    for repo in sources:
        name = repo["name"]
        data = fetch(f"/repos/{ORG}/{quote(name, safe='')}/languages")
        if not isinstance(data, dict) or any(
            not isinstance(language, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            for language, size in data.items()
        ):
            raise StatsError("Unexpected repository languages response")
        language_bytes.update(data)

    return Stats(
        repositories=len(sources),
        public=sum(repo.get("private") is False for repo in sources),
        private=sum(repo.get("private") is True for repo in sources),
        stars=sum(
            max(0, repo.get("stargazers_count", 0))
            for repo in sources
            if isinstance(repo.get("stargazers_count", 0), int)
            and not isinstance(repo.get("stargazers_count", 0), bool)
        ),
        pushed_90d=sum(_pushed_recently(repo.get("pushed_at"), now) for repo in sources),
        languages=dict(language_bytes),
    )


def _label(x: int, y: int, content: object, *, size: int, color: str, weight: int = 400) -> str:
    return (f'<text x="{x}" y="{y}" font-family="DejaVu Sans, Arial, sans-serif" '
            f'font-size="{size}" fill="{color}" font-weight="{weight}">{escape(str(content))}</text>')


def _frame(height: int, inner: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="630" '
        f'height="{height}" viewBox="0 0 630 {height}" role="img">'
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#082421"/>'
        '<stop offset="1" stop-color="#111722"/></linearGradient></defs>'
        f'<rect width="630" height="{height}" rx="14" fill="url(#bg)"/>'
        + inner + '</svg>\n'
    )


def render_overview(stats: Stats) -> str:
    fields = (
        ("REPOSITORIES", stats.repositories),
        ("PUBLIC", stats.public),
        ("PRIVATE", stats.private),
        ("STARS", stats.stars),
        ("PUSHED IN 90 DAYS", stats.pushed_90d),
        ("LANGUAGES", sum(value > 0 for value in stats.languages.values())),
    )
    parts = [
        _label(30, 42, "Violet-Void", size=25, color="#c7b8ff", weight=700),
        _label(30, 65, "Organization repository overview", size=13, color="#9dc4c1"),
    ]
    for i, (name, value) in enumerate(fields):
        x, y = 30 + (i % 3) * 205, 115 + (i // 3) * 76
        parts.append(_label(x, y, f"{value:,}", size=27, color="#f0f0f5", weight=700))
        parts.append(_label(x, y + 21, name, size=11, color="#7c60d1", weight=700))
    return _frame(229, "".join(parts))


def render_languages(stats: Stats) -> str:
    total = sum(stats.languages.values())
    parts = [
        _label(30, 42, "Violet-Void languages", size=25, color="#c7b8ff", weight=700),
        _label(30, 65, "Share of repository code bytes", size=13, color="#9dc4c1"),
    ]
    if total == 0:
        parts.append(_label(30, 133, "No language bytes reported", size=17, color="#f0f0f5"))
        return _frame(229, "".join(parts))

    colors = ["#fd7cff", "#319e8d", "#4b8afe", "#e6cd57", "#75c84a", "#e95c4a", "#7c60d1", "#6a7080"]
    top = sorted(((name, size) for name, size in stats.languages.items() if size > 0), key=lambda pair: (-pair[1], pair[0]))
    visible = top[:7]
    remaining = sum(size for _, size in top[7:])
    if remaining:
        visible.append(("Other", remaining))
    left = 30.0
    for i, (name, size) in enumerate(visible):
        width = (size / total) * 570
        parts.append(f'<rect x="{left:.2f}" y="86" width="{width:.2f}" height="14" fill="{colors[i]}"/>')
        left += width
        x = 30 + (i % 2) * 298
        y = 132 + (i // 2) * 26
        pct = size * 100 / total
        parts.append(f'<circle cx="{x + 6}" cy="{y - 5}" r="6" fill="{colors[i]}"/>')
        parts.append(_label(x + 20, y, f"{name[:24]} {pct:.1f}%", size=12, color="#f0f0f5"))
    return _frame(229, "".join(parts))


def publish(directory: Path, stats: Stats) -> None:
    # Render both completely before writing either file; failed collection must
    # never replace good images with zeros or errors.
    rendered = dict(zip(OUTPUTS, (render_overview(stats), render_languages(stats))))
    directory.mkdir(parents=True, exist_ok=True)
    for filename, content in rendered.items():
        target = directory / filename
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
        handle, temp = tempfile.mkstemp(prefix=".org-stats-", suffix=".tmp", dir=directory)
        try:
            os.fchmod(handle, mode)
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Violet-Void organization aggregate SVGs")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets" / "generated")
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    token = env.get("README_ORG_STATS_TOKEN")
    if not token:
        print("Missing README_ORG_STATS_TOKEN", file=sys.stderr)
        return 2
    try:
        stats = collect(github_fetch(token))
        publish(args.output_dir, stats)
    except (StatsError, OSError) as exc:
        print(f"Organization stats unavailable: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
