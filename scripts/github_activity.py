from __future__ import annotations

import html
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.readme_config import (
    ALLOWED_OWNERS,
    AUTHOR_LOGIN,
    CONTRIB_LIMIT,
    CONTRIB_REPO_LIMIT,
    MAX_HISTORY_PAGES,
    MAX_PR_PAGES,
    PAGE_SIZE,
    PROFILE_TIMEZONE,
    PR_LIMIT,
    PROFILE_REPO,
)
from scripts.http_json import HttpJsonTransportError, request_json

GRAPHQL_URL = "https://api.github.com/graphql"
WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

PR_QUERY = """
query($login: String!, $first: Int!, $after: String) {
  user(login: $login) {
    pullRequests(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        title
        url
        state
        createdAt
        repository {
          nameWithOwner
          isPrivate
          url
          description
          owner { login }
        }
      }
    }
  }
}
"""

CONTRIB_QUERY = """
query($login: String!) {
  viewer {
    login
  }
  user(login: $login) {
    id
    contributionsCollection {
      startedAt
      endedAt
      commitContributionsByRepository(maxRepositories: {CONTRIB_REPO_LIMIT}) {
        contributions { totalCount }
        repository {
          nameWithOwner
          isPrivate
          url
          description
          owner { login }
        }
      }
    }
  }
}
""".replace("{CONTRIB_REPO_LIMIT}", str(CONTRIB_REPO_LIMIT))

HISTORY_QUERY = """
query(
  $owner: String!, $name: String!, $authorId: ID!, $since: GitTimestamp!,
  $until: GitTimestamp!, $after: String
) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(
            first: 100, after: $after, author: {id: $authorId}, since: $since, until: $until
          ) {
            pageInfo { hasNextPage endCursor }
            nodes { committedDate }
          }
        }
      }
    }
  }
}
"""


class ActivityCollectionError(Exception):
    """Raised when GitHub activity cannot be collected."""


HttpCallable = Callable[..., dict[str, Any]]


@dataclass
class PublicPR:
    title: str
    url: str
    state: str
    created_at: str
    repo_url: str
    repo_name: str
    description: str | None


@dataclass
class PublicContrib:
    repo_url: str
    repo_name: str
    count: int
    description: str | None
    latest_at: str | None


@dataclass
class ActivityModel:
    public_prs: list[PublicPR]
    public_contribs: list[PublicContrib]
    private_pr_count: int | None
    private_commit_count: int | None
    commit_hours: dict[str, int] | None = None
    commit_weekdays: dict[str, int] | None = None
    contribution_repos_bounded: bool = False


def default_http(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return request_json(url, method=method, headers=headers, json_body=json_body)
    except HttpJsonTransportError as exc:
        raise ActivityCollectionError("GitHub request failed") from exc


def _graphql(
    http: HttpCallable,
    token: str,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "aaronedev-readme",
    }
    body: dict[str, Any] = {"query": query}
    if variables is not None:
        body["variables"] = variables
    response = http(GRAPHQL_URL, method="POST", headers=headers, json_body=body)
    status = response.get("status")
    payload = response.get("json")
    if status != 200:
        raise ActivityCollectionError(
            f"GitHub GraphQL request failed with HTTP {status}"
        )
    if not isinstance(payload, dict):
        raise ActivityCollectionError("GitHub GraphQL returned an unexpected payload")
    if payload.get("errors"):
        raise ActivityCollectionError("GitHub GraphQL returned errors")
    if "data" not in payload:
        raise ActivityCollectionError("GitHub GraphQL returned no data")
    return payload


def _owner_login(repo: dict[str, Any] | None) -> str | None:
    if not isinstance(repo, dict):
        return None
    owner = repo.get("owner")
    if isinstance(owner, dict):
        login = owner.get("login")
        return login if isinstance(login, str) and login else None
    return None


def _public_http_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _has_required_pr_fields(node: dict[str, Any]) -> bool:
    if not isinstance(node, dict):
        return False
    repo = node.get("repository")
    if not isinstance(repo, dict):
        return False
    return bool(
        node.get("title")
        and _public_http_url(node.get("url"))
        and node.get("state")
        and node.get("createdAt")
        and _public_http_url(repo.get("url"))
        and repo.get("nameWithOwner")
        and _owner_login(repo)
    )


def _has_required_contrib_fields(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    repo = entry.get("repository")
    if not isinstance(repo, dict):
        return False
    return bool(
        repo.get("nameWithOwner")
        and _public_http_url(repo.get("url"))
        and _owner_login(repo)
    )


def _split_name_with_owner(name_with_owner: str) -> tuple[str, str] | None:
    if not isinstance(name_with_owner, str) or "/" not in name_with_owner:
        return None
    owner, name = name_with_owner.split("/", 1)
    if not owner or not name or "/" in name:
        return None
    return owner, name


def _allowlisted_timing_repos(*groups: list[dict[str, Any]]) -> list[str]:
    """Use proven public/private entries from the bounded response; no extra repo query."""
    names: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            repo = item.get("repository") if isinstance(item, dict) else None
            if not isinstance(repo, dict):
                continue
            name = repo.get("nameWithOwner")
            if (
                not isinstance(name, str)
                or name in seen
                or _owner_login(repo) not in ALLOWED_OWNERS
                or repo.get("isPrivate") not in {False, True}
            ):
                continue
            seen.add(name)
            names.append(name)
    return names


def _collect_commit_dates(
    http: HttpCallable,
    token: str,
    author_id: str,
    repos: list[str],
    since: str,
    until: str,
) -> dict[str, list[str]]:
    dates_by_repo: dict[str, list[str]] = {}
    for name_with_owner in repos:
        parts = _split_name_with_owner(name_with_owner)
        if parts is None:
            continue
        owner, name = parts
        after: str | None = None
        seen_cursors: set[str] = set()
        repo_dates: list[str] = []
        for _page in range(MAX_HISTORY_PAGES):
            payload = _graphql(
                http,
                token,
                HISTORY_QUERY,
                {
                    "owner": owner,
                    "name": name,
                    "authorId": author_id,
                    "since": since,
                    "until": until,
                    "after": after,
                },
            )
            repository = ((payload.get("data") or {}).get("repository")) or {}
            history = (
                ((repository.get("defaultBranchRef") or {}).get("target") or {}).get("history")
                or {}
            )
            for node in history.get("nodes") or []:
                if isinstance(node, dict) and isinstance(node.get("committedDate"), str):
                    repo_dates.append(node["committedDate"])
            page_info = history.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                raise ActivityCollectionError("GitHub commit history pagination is incomplete")
            seen_cursors.add(cursor)
            after = cursor
        else:
            raise ActivityCollectionError("GitHub commit history exceeded page limit")
        dates_by_repo[name_with_owner] = repo_dates
    return dates_by_repo


def retrieve(http: HttpCallable, token: str) -> dict[str, Any]:
    pull_requests: list[dict[str, Any]] = []
    after: str | None = None
    seen_cursors: set[str] = set()
    for _page in range(MAX_PR_PAGES):
        payload = _graphql(
            http,
            token,
            PR_QUERY,
            {"login": AUTHOR_LOGIN, "first": PAGE_SIZE, "after": after},
        )
        user = ((payload.get("data") or {}).get("user")) or {}
        connection = user.get("pullRequests") or {}
        nodes = connection.get("nodes") or []
        for node in nodes:
            if isinstance(node, dict):
                pull_requests.append(node)
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
            raise ActivityCollectionError("GitHub pull request pagination is incomplete")
        seen_cursors.add(cursor)
        after = cursor
    else:
        raise ActivityCollectionError("GitHub pull request pagination exceeded page limit")

    contrib_payload = _graphql(http, token, CONTRIB_QUERY, {"login": AUTHOR_LOGIN})
    data = contrib_payload.get("data") or {}
    viewer = data.get("viewer") or {}
    viewer_login = viewer.get("login") if isinstance(viewer, dict) else None
    if not isinstance(viewer_login, str) or viewer_login.casefold() != AUTHOR_LOGIN.casefold():
        raise ActivityCollectionError("GitHub viewer does not match configured author")
    author = data.get("user") or {}
    collection = author.get("contributionsCollection") if isinstance(author, dict) else None
    if not isinstance(collection, dict):
        raise ActivityCollectionError("GitHub author contribution collection is unavailable")
    raw_contribs = collection.get(
        "commitContributionsByRepository"
    ) or []
    contributions = [item for item in raw_contribs if isinstance(item, dict)]
    author_id = author.get("id") if isinstance(author.get("id"), str) else None
    if not author_id:
        raise ActivityCollectionError("GitHub author ID is unavailable")
    since = collection.get("startedAt")
    until = collection.get("endedAt")
    if not isinstance(since, str) or not isinstance(until, str):
        raise ActivityCollectionError("GitHub contribution window is unavailable")
    # A public-only timing list would undercount known private contributions.
    history_repos = _allowlisted_timing_repos(pull_requests, contributions)
    commit_dates_by_repo = _collect_commit_dates(
        http, token, author_id, history_repos, since, until
    )
    return {
        "pull_requests": pull_requests,
        "contributions": contributions,
        "commit_dates": [date for dates in commit_dates_by_repo.values() for date in dates],
        "commit_dates_by_repo": commit_dates_by_repo,
        "contribution_repos_bounded": len(contributions) >= CONTRIB_REPO_LIMIT,
    }


def _contrib_count(entry: dict[str, Any]) -> int | None:
    if "contributionCount" in entry and entry["contributionCount"] is not None:
        try:
            return int(entry["contributionCount"])
        except (TypeError, ValueError):
            return None
    total = (entry.get("contributions") or {}).get("totalCount")
    if total is None:
        return None
    try:
        return int(total)
    except (TypeError, ValueError):
        return None


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ActivityCollectionError("activity payload is not an object")
    pull_requests = raw.get("pull_requests")
    if pull_requests is None:
        pull_requests = (
            ((raw.get("data") or {}).get("user") or {}).get("pullRequests") or {}
        ).get("nodes") or []
    contributions = raw.get("contributions")
    if contributions is None:
        data = raw.get("data") or {}
        collection = ((data.get("user") or {}).get("contributionsCollection"))
        if collection is None:
            collection = ((data.get("viewer") or {}).get("contributionsCollection"))
        contributions = (collection or {}).get("commitContributionsByRepository") or []
    normalized_prs = [item for item in pull_requests if isinstance(item, dict)]
    normalized_contribs: list[dict[str, Any]] = []
    for item in contributions:
        if not isinstance(item, dict):
            continue
        count = _contrib_count(item)
        normalized_contribs.append(
            {
                "contributionCount": count,
                "repository": item.get("repository")
                if isinstance(item.get("repository"), dict)
                else {},
            }
        )
    commit_dates = [
        item for item in (raw.get("commit_dates") or []) if isinstance(item, str)
    ]
    commit_dates_by_repo: dict[str, list[str]] = {}
    raw_dates_by_repo = raw.get("commit_dates_by_repo") or {}
    if isinstance(raw_dates_by_repo, dict):
        for name, dates in raw_dates_by_repo.items():
            if isinstance(name, str) and isinstance(dates, list):
                commit_dates_by_repo[name] = [date for date in dates if isinstance(date, str)]
    raw_bounded = raw.get("contribution_repos_bounded")
    contribution_repos_bounded = (
        raw_bounded
        if isinstance(raw_bounded, bool)
        else len(normalized_contribs) >= CONTRIB_REPO_LIMIT
    )
    return {
        "pull_requests": normalized_prs,
        "contributions": normalized_contribs,
        "commit_dates": commit_dates,
        "commit_dates_by_repo": commit_dates_by_repo,
        "contribution_repos_bounded": contribution_repos_bounded,
    }


def _parse_dt(value: str) -> datetime | None:
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hour_bucket(hour: int) -> str:
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "daytime"
    if 18 <= hour < 24:
        return "evening"
    return "night"


def _aggregates(
    commit_dates: list[str],
) -> tuple[dict[str, int] | None, dict[str, int] | None]:
    try:
        profile_timezone = ZoneInfo(PROFILE_TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        raise ActivityCollectionError(
            f"invalid profile timezone: {PROFILE_TIMEZONE}"
        ) from exc
    if not commit_dates:
        return None, None
    hours = {"morning": 0, "daytime": 0, "evening": 0, "night": 0}
    weekdays = {name: 0 for name in WEEKDAYS}
    found = False
    for value in commit_dates:
        parsed = _parse_dt(value)
        if parsed is None:
            continue
        local = parsed.astimezone(profile_timezone)
        found = True
        hours[_hour_bucket(local.hour)] += 1
        weekdays[WEEKDAYS[local.weekday()]] += 1
    if not found:
        return None, None
    return hours, weekdays


def _sort_ts(value: str | None) -> float:
    if not value:
        return 0.0
    parsed = _parse_dt(value)
    return parsed.timestamp() if parsed else 0.0


def privacy_reduce(normalized: dict[str, Any]) -> ActivityModel:
    public_prs: list[PublicPR] = []
    seen_pr_urls: set[str] = set()
    private_pr_count = 0
    private_commit_count = 0
    proven_private_prs = False
    proven_private_commits = False

    for node in normalized.get("pull_requests") or []:
        repo = node.get("repository") if isinstance(node, dict) else None
        if not isinstance(repo, dict):
            continue
        owner = _owner_login(repo)
        if owner not in ALLOWED_OWNERS:
            continue
        if repo.get("isPrivate") is True:
            proven_private_prs = True
            private_pr_count += 1
            continue
        if repo.get("isPrivate") is not False:
            continue
        if not _has_required_pr_fields(node):
            continue
        url = node["url"]
        if url in seen_pr_urls:
            continue
        seen_pr_urls.add(url)
        description = repo.get("description")
        public_prs.append(
            PublicPR(
                title=str(node["title"]),
                url=str(url),
                state=str(node["state"]),
                created_at=str(node["createdAt"]),
                repo_url=str(repo["url"]),
                repo_name=str(repo["nameWithOwner"]),
                description=str(description) if description else None,
            )
        )

    contribs_by_name: dict[str, PublicContrib] = {}
    for entry in normalized.get("contributions") or []:
        repo = entry.get("repository") if isinstance(entry, dict) else None
        if not isinstance(repo, dict):
            continue
        owner = _owner_login(repo)
        if owner not in ALLOWED_OWNERS:
            continue
        count = entry.get("contributionCount")
        try:
            count_int = int(count) if count is not None else 0
        except (TypeError, ValueError):
            count_int = 0
        if repo.get("isPrivate") is True:
            proven_private_commits = True
            private_commit_count += max(count_int, 0)
            continue
        if repo.get("isPrivate") is not False:
            continue
        name = repo.get("nameWithOwner")
        if name == PROFILE_REPO:
            continue
        if not _has_required_contrib_fields(entry):
            continue
        description = repo.get("description")
        repo_dates = (normalized.get("commit_dates_by_repo") or {}).get(str(name), [])
        latest_at = max(
            (date for date in repo_dates if _parse_dt(date) is not None),
            key=_sort_ts,
            default=None,
        )
        existing = contribs_by_name.get(str(name))
        if existing is not None:
            existing.count += count_int
            if _sort_ts(latest_at) > _sort_ts(existing.latest_at):
                existing.latest_at = latest_at
            continue
        contribs_by_name[str(name)] = PublicContrib(
            repo_url=str(repo["url"]),
            repo_name=str(name),
            count=count_int,
            description=str(description) if description else None,
            latest_at=latest_at,
        )

    public_prs.sort(key=lambda item: (-_sort_ts(item.created_at), item.url))
    public_prs = public_prs[:PR_LIMIT]
    public_contribs = list(contribs_by_name.values())
    public_contribs.sort(
        key=lambda item: (
            item.latest_at is None,
            -_sort_ts(item.latest_at),
            item.repo_name,
        )
    )
    public_contribs = public_contribs[:CONTRIB_LIMIT]
    commit_hours, commit_weekdays = _aggregates(normalized.get("commit_dates") or [])
    return ActivityModel(
        public_prs=public_prs,
        public_contribs=public_contribs,
        private_pr_count=private_pr_count if proven_private_prs else None,
        private_commit_count=private_commit_count if proven_private_commits else None,
        commit_hours=commit_hours,
        commit_weekdays=commit_weekdays,
        contribution_repos_bounded=bool(normalized.get("contribution_repos_bounded")),
    )


def _clean_text(value: str | None, *, limit: int | None = None) -> str:
    if not value:
        return ""
    text = value
    if limit is not None and len(text) > limit:
        text = text[:limit]
    return html.escape(text, quote=True)


def _state_emoji(state: str) -> str:
    if state == "OPEN":
        return "🟣"
    if state == "MERGED":
        return "🟢"
    return "⚫"


def _iso_date(value: str) -> str:
    parsed = _parse_dt(value)
    if parsed is not None:
        return parsed.date().isoformat()
    return value[:10] if len(value) >= 10 else value


def render(model: ActivityModel) -> str:
    lines: list[str] = ["### 🔁 Fresh Pull Requests", ""]
    if not model.public_prs:
        lines.append("_No public pull requests from allowed owners._")
        lines.append("")
    else:
        for pr in model.public_prs:
            title = _clean_text(pr.title)
            emoji = _state_emoji(pr.state)
            lines.append(
                f'- {emoji} <a href="{html.escape(pr.url, quote=True)}"><strong>{title}</strong></a><br>'
            )
            lines.append(
                "  <sub>"
                f'<a href="{html.escape(pr.repo_url, quote=True)}"><code>{html.escape(pr.repo_name, quote=True)}</code></a>'
                f" • {_iso_date(pr.created_at)} • {html.escape(pr.state, quote=True)}"
                "</sub>"
            )
            description = _clean_text(pr.description, limit=120)
            if description:
                lines.append("  <br>")
                lines.append(f"  <sub>{description}</sub>")
            lines.append("")

    lines.append("### 🛠️ Latest Contributions")
    lines.append("")
    if not model.public_contribs:
        lines.append("_No public commits from allowed owners._")
        lines.append("")
    else:
        for contrib in model.public_contribs:
            label = "commit" if contrib.count == 1 else "commits"
            lines.append(
                "- 🔗 "
                f'<a href="{html.escape(contrib.repo_url, quote=True)}"><code>{html.escape(contrib.repo_name, quote=True)}</code></a>'
                f" • <strong>{contrib.count} {label}</strong>"
                + (f" • {_iso_date(contrib.latest_at)}" if contrib.latest_at else "")
            )
            description = _clean_text(contrib.description, limit=120)
            if description:
                lines.append("  <br>")
                lines.append(f"  <sub>{description}</sub>")
            lines.append("")

    if model.contribution_repos_bounded:
        lines.append("_GitHub activity is based on the top 100 contribution repositories._")
        lines.append("")

    private_parts: list[str] = []
    if model.private_pr_count:
        label = "pull request" if model.private_pr_count == 1 else "pull requests"
        private_parts.append(f"{model.private_pr_count} {label}")
    if model.private_commit_count:
        label = "commit" if model.private_commit_count == 1 else "commits"
        prefix = "at least " if model.contribution_repos_bounded else ""
        private_parts.append(f"{prefix}{model.private_commit_count} {label}")
    if private_parts:
        lines.append(f"🔒 Private activity: {' · '.join(private_parts)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
