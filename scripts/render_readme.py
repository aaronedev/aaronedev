from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import stat
from pathlib import Path
from typing import Mapping

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.github_activity import (
    ActivityCollectionError,
    ActivityModel,
    default_http as github_http,
    normalize,
    privacy_reduce,
    render as render_activity,
    retrieve as retrieve_activity,
)
from scripts.readme_config import (
    ACTIVITY_END,
    ACTIVITY_START,
    WAKA_END,
    WAKA_START,
)
from scripts.wakatime_stats import (
    WAKA_SECTION_MARKER,
    WakaCollectionError,
    default_http as waka_http,
    render as render_waka,
    retrieve as retrieve_waka,
)

EXIT_OK = 0
EXIT_COLLECTOR_FAILED = 2
ACTIVITY_FALLBACK = "\n_Activity temporarily unavailable._\n"
WAKA_FALLBACK = "\n_WakaTime stats temporarily unavailable._\n"


def extract_section(text: str, start: str, end: str) -> str | None:
    if not text:
        return None
    start_at = text.find(start)
    end_at = text.find(end)
    if start_at == -1 or end_at == -1 or end_at < start_at:
        return None
    return text[start_at + len(start) : end_at]


def replace_section(text: str, start: str, end: str, inner: str) -> str:
    start_at = text.find(start)
    end_at = text.find(end)
    if start_at == -1 or end_at == -1 or end_at < start_at:
        raise ValueError(f"missing markers {start} / {end}")
    return text[: start_at + len(start)] + inner + text[end_at:]


def _wrap_new(markdown: str) -> str:
    body = markdown if markdown.startswith("\n") else "\n" + markdown
    if not body.endswith("\n"):
        body += "\n"
    return body


def _safe_previous_waka(existing: str) -> str:
    # The version marker is the ownership boundary; legacy text cannot be safely inferred.
    previous = extract_section(existing, WAKA_START, WAKA_END)
    if previous is not None and (
        previous.startswith(WAKA_SECTION_MARKER)
        or previous.startswith("\n" + WAKA_SECTION_MARKER)
    ):
        return previous
    return WAKA_FALLBACK


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    handle, tmp_name = tempfile.mkstemp(
        prefix=".readme-", suffix=".tmp", dir=str(path.parent)
    )
    try:
        if existing_mode is not None:
            os.fchmod(handle, existing_mode)
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as tmp:
            tmp.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def render_readme(
    repo_root: Path,
    *,
    activity_markdown: str,
    waka_markdown: str,
    output: Path | None = None,
) -> str:
    root = Path(repo_root)
    template = (root / "templates" / "README.md.tpl").read_text(encoding="utf-8")
    text = replace_section(
        template, ACTIVITY_START, ACTIVITY_END, _wrap_new(activity_markdown)
    )
    text = replace_section(text, WAKA_START, WAKA_END, _wrap_new(waka_markdown))
    dest = Path(output) if output is not None else root / "README.md"
    _atomic_write(dest, text)
    return text


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture must be a JSON object")
    return payload


def _collect_activity(
    fixture: Path | None,
    environ: Mapping[str, str],
) -> tuple[str, dict[str, int] | None, dict[str, int] | None, bool]:
    if fixture is not None:
        model: ActivityModel = privacy_reduce(normalize(_load_json(fixture)))
        return (
            render_activity(model),
            model.commit_hours,
            model.commit_weekdays,
            model.contribution_repos_bounded,
        )
    token = (
        environ.get("README_ACTIVITY_GITHUB_PAT")
        or environ.get("GH_TOKEN")
        or environ.get("GITHUB_TOKEN")
    )
    if not token:
        raise ActivityCollectionError("missing README_ACTIVITY_GITHUB_PAT")
    model = privacy_reduce(normalize(retrieve_activity(github_http, token)))
    return (
        render_activity(model),
        model.commit_hours,
        model.commit_weekdays,
        model.contribution_repos_bounded,
    )


def _collect_waka(
    fixture: Path | None,
    environ: Mapping[str, str],
    commit_hours: dict[str, int] | None,
    commit_weekdays: dict[str, int] | None,
    contribution_repos_bounded: bool = False,
) -> str:
    if fixture is not None:
        payload = _load_json(fixture)

        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": payload}

        stats = retrieve_waka(http, api_key="fixture")
        return render_waka(
            stats,
            commit_hours=commit_hours,
            commit_weekdays=commit_weekdays,
            contribution_repos_bounded=contribution_repos_bounded,
        )
    api_key = environ.get("README_WAKATIME_API_KEY") or environ.get("WAKATIME_API_KEY")
    if not api_key:
        raise WakaCollectionError("missing README_WAKATIME_API_KEY")
    stats = retrieve_waka(waka_http, api_key)
    return render_waka(
        stats,
        commit_hours=commit_hours,
        commit_weekdays=commit_weekdays,
        contribution_repos_bounded=contribution_repos_bounded,
    )


def main(
    argv: list[str] | None = None, environ: Mapping[str, str] | None = None
) -> int:
    parser = argparse.ArgumentParser(
        description="Render README.md from the local template."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--fixture-activity", type=Path, default=None)
    parser.add_argument("--fixture-waka", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    env = os.environ if environ is None else environ
    root = args.repo_root or _ROOT
    output = args.output or (root / "README.md")
    existing = output.read_text(encoding="utf-8") if output.exists() else ""

    failed = False
    commit_hours = None
    commit_weekdays = None
    contribution_repos_bounded = False
    activity_succeeded = False
    try:
        (
            activity_md,
            commit_hours,
            commit_weekdays,
            contribution_repos_bounded,
        ) = _collect_activity(args.fixture_activity, env)
        activity_inner = _wrap_new(activity_md)
        activity_succeeded = True
    except (ActivityCollectionError, OSError, ValueError, json.JSONDecodeError):
        failed = True
        previous = extract_section(existing, ACTIVITY_START, ACTIVITY_END)
        activity_inner = previous if previous is not None else ACTIVITY_FALLBACK

    try:
        if not activity_succeeded:
            raise WakaCollectionError("GitHub activity collection failed")
        waka_md = _collect_waka(
            args.fixture_waka,
            env,
            commit_hours,
            commit_weekdays,
            contribution_repos_bounded,
        )
        waka_inner = _wrap_new(waka_md)
    except (WakaCollectionError, OSError, ValueError, json.JSONDecodeError):
        failed = True
        waka_inner = _safe_previous_waka(existing)

    render_readme(
        root,
        activity_markdown=activity_inner,
        waka_markdown=waka_inner,
        output=output,
    )
    return EXIT_COLLECTOR_FAILED if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
